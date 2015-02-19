import sys, os
sys.path.append("..")

import collections, shutil
import urllib2, collections, demjson
from urllib import urlencode
from redis import WatchError
from tempfile import NamedTemporaryFile
from lxml import etree
from bs4 import BeautifulSoup
import zipfile

import config_utils
from dao.dictsearchstore import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApplicationIdLocker:
	def __init__(self, db, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.db = db
		self.app_id = None

	def __lock_app_id(self, key, field, value):
		"""Get a simple lock on a specific app_id in Redis."""
		lock_name = ':'.join((self.alphabet.lock_prefix(), field))

		logger.info('Lock name: %s' % lock_name)

		# Check lock. If not locked, get lock.
		lock_result = self.db.set(lock_name, 1, nx=True, ex=3600)
		logger.debug('Lock result for key %s: %s' % (key, lock_result))
		if not lock_result:
			return False

		try:
			with self.db.pipeline() as pipe:
				pipe.watch(lock_name)
				pipe.multi()
				pipe.hset(key, field, config_utils.current_time_millis())
				pipe.execute()
				return True
		except WatchError:
				return False

	def need_fetch(self, value):
		"""Checks if the app_id timestamp is 0 (never fetched) or old."""
		value = int(value)
		return value == 0 or value < config_utils.current_time_millis() - 1000000

	def set_lock_get_id(self):
		"""Get an app_id that isn't currently locked for fetching."""
		key = self.alphabet.name

		for field, value in self.db.hscan_iter(key, count=20):
			# Check if value is stale
			if self.need_fetch(value) and self.__lock_app_id(key, field, value):
				logger.info('Got app_id lock: %s', field)
				self.app_id = field
				return field

			logger.debug('App_id %s was locked. Trying next...' % field)

		logger.warn('Could not find any unlocked and/or stale app_id!')

	def unlock(self):
		"""Release the lock on an app_id."""
		if not self.app_id:
			return

		lock_name = ':'.join((self.alphabet.lock_prefix(), self.app_id))
		result = self.db.delete(lock_name)
		logger.info('Attempted release of lock: %s (result: %s)' % (lock_name, result))
		return result


class GitRepositoryHandler:
	def __init__(self):
		pass

	def commit(self, metadata, dir):
		logger.info(metadata.print_all())
		logger.info('Committing all changes in: %s' % dir)


class ChromePackageFetcher:

	def reset_url_params(self):
		self.url_params = collections.OrderedDict([
			('response', 'redirect'),
			('prodchannel', 'unknown'),
			('prodversion', '9999.0.9999.0'),
			('x=id', None),
			('lang', None)
		])

	def __init__(self, url, db, git_dir, crx_dir, metadata_fetcher, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.db = db
		self.fetch_point = url
		self.reset_url_params()
		self.app_id_locker = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.git_dir = git_dir
		self.crx_dir = crx_dir
		self.git_handler = GitRepositoryHandler()
		self.metadata_fetcher = metadata_fetcher

	def build_fetch_url(self, app_id):
		"""Returns download url for the given app_id."""
		self.url_params['x=id'] = app_id + '&uc'
		self.url_params['lang'] = self.alphabet.hyphenated()

		# Chrome download API is picky about making sure the = in '&x='
		# is NOT escaped, but urlencode() escapes it. So replace it
		return '?'.join((self.fetch_point, urlencode(self.url_params).replace('&x%3D', '&x=')))

	def get_request(self, url):
		"""Simple wrapper to GET url. Returns response."""
		request = urllib2.Request(url, headers=config_utils.FETCHER_HTTP_HEADERS)
		return urllib2.urlopen(request)

	def get_dl_path_from_response(self, app_id, response):
		"""Given an app_id and urllib2 response, generate the
		local file name to save the response results to.
		"""
		filename = response.geturl().split('/')[-1]
		app_path = os.path.join(self.crx_dir, app_id, filename)

		if not os.path.exists(os.path.dirname(app_path)):
			os.makedirs(os.path.dirname(app_path))
		return app_path

	def get_crx_extract_path(self, app_id):
		"""Get the extraction path for extracting crx to git repo."""
		return os.path.join(self.git_dir, app_id)

	def extract_crx(self, crx_path, app_id):
		"""Extract crx at crx_path into the configured git directory
		for this class.

		Returns the target directory where the crx was extracted.
		"""
		with zipfile.ZipFile(crx_path, 'r') as zf:
			extract_path = self.get_crx_extract_path(app_id)
			zf.extractall(extract_path)
			logger.info('Extracted app %s to %s' % (app_id, extract_path))
			return extract_path

	def fetch_app(self, app_id):
		"""Downloads the app_id .crx file to a local location.

		Return location of crx, and location of extracted files.
		"""
		dl_url = self.build_fetch_url(app_id)
		logger.info('Fetching from url: %s' % dl_url)
		response = self.get_request(dl_url)

		assert response.code == 200, 'Tried fetching %s, but got response code: %s' % (app_id, response.code)

		app_path = self.get_dl_path_from_response(app_id, response)

		with open(app_path, 'wb') as fp:
			shutil.copyfileobj(response, fp)
			logger.info('Wrote application crx to: %s' % fp.name)

		return (app_path, self.extract_crx(app_path, app_id))

	def run(self):
		app_id = None
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.app_id_locker.set_lock_get_id()

			# Fetch app
			app_path, extract_path = self.fetch_app(app_id)

			# Fetch metadata
			metadata = self.metadata_fetcher.fetch_tags(app_id)

			# Commit to git repo
			self.git_handler.commit(metadata, extract_path)

			import time
			print 'sleeping for 3 secs to simulate fetching duration'
			time.sleep(3)

			# Release lock
		finally:
			self.app_id_locker.unlock()


class MetadataFetcher:
	"""Metadata fetching and storing functionality"""

	def __init__ (self, base_url):
		self.base_url = base_url

	def generate_url(self, app_id):
		return self.base_url + app_id

	def get_app_page(self, app_id):
		response = urllib2.urlopen(self.generate_url(app_id))
		return response.read()

	def fetch_tags(self, app_id):
		tree = etree.HTML(self.get_app_page(app_id))
		m = tree.xpath("//meta")
		metadata = AppMetadata(app_id)

		for i in m:
			if etree.tostring(i).find("itemprop") != -1:
				soup = BeautifulSoup(etree.tostring(i))
				for meta_tag in soup('meta'):
					if meta_tag['itemprop'] == 'name':
						metadata.name = meta_tag['content']
					elif meta_tag['itemprop'] == 'url':
						metadata.url = meta_tag['content']
					elif meta_tag['itemprop'] == 'version':
						metadata.version = meta_tag['content']
					elif meta_tag['itemprop'] == 'price':
						metadata.price = meta_tag['content'][1:]
					elif meta_tag['itemprop'] == 'interactionCount':
						if(meta_tag['content'].find("UserDownloads") != -1):
						 	metadata.downloads = meta_tag['content'][14:]
						else:
						 	metadata.downloads = 0

					elif meta_tag['itemprop'] == 'operatingSystems':
						metadata.os = meta_tag['content']
					elif meta_tag['itemprop'] == 'ratingValue':
						metadata.ratingValue = meta_tag['content']
					elif meta_tag['itemprop'] == 'ratingCount':
						metadata.ratingCount = meta_tag['content']
					elif meta_tag['itemprop'] == 'priceCurrency':
						metadata.priceCurrency = meta_tag['content']
		return metadata


class AppMetadata:
	"""Contains name, url, version, price, priceCurrency, 
	downloads, os, ratingValue, ratingCount and priceCurrency.
	"""

	def __init__(self, app_id):
		self.app_id = app_id

	def print_all(self):
		import pprint
		pprint.pprint(vars(self))
