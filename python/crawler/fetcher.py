#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import collections, shutil
import urllib2, collections, demjson
from urllib import urlencode
from tempfile import NamedTemporaryFile
from lxml import etree
from bs4 import BeautifulSoup
import zipfile
from sh import git, ErrorReturnCode_1

import config_utils
from dao.dictsearchstore import *
from synchronization.locking import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitRepositoryHandler(object):
	git_user = "chromecrawler"
	git_email = "test@test.com"

	def __init__(self):
		pass

	def init_repo(self, dir):
		os.chdir(dir)
		git.init()
		logger.debug("Invoked git init for %s" % dir)

	def set_config(self):
		git.config("user.name %s" % self.git_user)
		git.config("user.email %s" % self.git_email)

	def commit(self, metadata, dir):
		os.chdir(dir)
		logger.info(metadata.to_pretty_value())
		git.add("--all")
		try:
			git.commit("-m %s" % metadata.to_pretty_value())
			logger.info('Committed all changes in: %s' % dir)
			return True
		except ErrorReturnCode_1:
			if 'nothing to commit' in traceback.format_exc():
				logger.info('Nothing to commit')
				return False
			else:
				logger.error(traceback.format_exc())
				return False


class ChromePackageFetcher(object):
	"""Class that abstracts away the act of:

	- Getting the next app_id from the db
	- Fetching the crx for the app_id
	- Fetching metadata for the app_id
	- Committing the metadata and extracted app to git dir
	"""

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
		response = self.get_request(dl_url)
		logger.info('Fetched from url: %s --- response code was: %s' % (dl_url, response.code))

		if response.code != 200:
			return (None, None)

		app_path = self.get_dl_path_from_response(app_id, response)

		with open(app_path, 'wb') as fp:
			shutil.copyfileobj(response, fp)
			logger.info('Wrote application crx to: %s' % fp.name)

		return (app_path, self.extract_crx(app_path, app_id))

	def run(self, app_id=None):
		# Fetch app
		app_path, extract_path = self.fetch_app(app_id)
		metadata = None

		if app_path:
			# Fetch metadata
			metadata = self.metadata_fetcher.fetch_tags(app_id)

			# Commit to git repo
			self.git_handler.init_repo(extract_path)
			if not self.git_handler.commit(metadata, extract_path):
				return None

		return metadata


class MetadataFetcher(object):
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
						metadata.rating_value = meta_tag['content']
					elif meta_tag['itemprop'] == 'ratingCount':
						metadata.rating_count = meta_tag['content']
					elif meta_tag['itemprop'] == 'priceCurrency':
						metadata.price_currency = meta_tag['content']
		return metadata


class AppMetadata(object):
	"""Contains name, url, version, price, priceCurrency, 
	downloads, os, ratingValue, ratingCount and priceCurrency.
	"""
	report_type = 'AppMetadata'

	def __init__(self, app_id):
		self.app_id = app_id
		self.name = None
		self.url = None
		self.version = None
		self.price = None
		self.downloads = None
		self.os = None
		self.rating_value = None
		self.rating_count = None
		self.price_currency = None

	def to_pretty_value(self, indent=4, sort_keys=True):
		instance_vars = vars(self)
		instance_vars['__type__'] = 'AppMetadata'

		return json.dumps(instance_vars, indent=indent, sort_keys=sort_keys)

	def print_all(self):
		"""Useful for debugging."""
		import pprint
		pprint.pprint(vars(self))

	def generate_report(self):
		return vars(self)
