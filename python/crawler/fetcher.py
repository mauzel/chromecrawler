import sys, os
sys.path.append("..")

import collections, shutil
import config_utils
import urllib2, collections, demjson
from urllib import urlencode
from dao.dictsearchstore import *
from redis import WatchError
from tempfile import NamedTemporaryFile

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


class ChromePackageFetcher:

	def reset_url_params(self):
		self.url_params = collections.OrderedDict([
			('response', 'redirect'),
			('prodchannel', 'unknown'),
			('prodversion', '9999.0.9999.0'),
			('x=id', None),
			('lang', None),
			('prodversion', '32')
		])

	def __init__(self, url, db, git_dir, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.db = db
		self.fetch_point = url
		logger.info('Fetch point: %s' % self.fetch_point)
		self.reset_url_params()
		self.app_id_locker = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.git_dir = git_dir

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
		app_path = os.path.join(self.git_dir, app_id, filename)

		if not os.path.exists(os.path.dirname(app_path)):
			os.makedirs(os.path.dirname(app_path))
		return app_path

	def fetch_app(self, app_id):
		"""Downloads the app_id .crx file to a local location."""
		dl_url = self.build_fetch_url(app_id)
		logger.info('Fetching from url: %s' % dl_url)
		response = self.get_request(dl_url)

		assert response.code == 200, 'Tried fetching %s, but got response code: %s' % (app_id, response.code)

		app_path = self.get_dl_path_from_response(app_id, response)

		with open(app_path, 'wb') as fp:
			logger.info('Writing .crx to: %s' % app_path)
			shutil.copyfileobj(response, fp)
			logger.info('Wrote application to: %s' % fp.name)

			import time
			print 'sleeping for 10 secs to simulate fetching duration'
			time.sleep(10)

	def run(self):
		app_id = None
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.app_id_locker.set_lock_get_id()

			# Fetch data about that app
			self.fetch_app(app_id)

			# Release lock
		finally:
			self.app_id_locker.unlock()