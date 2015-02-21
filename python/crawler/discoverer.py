#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append("..")

import urllib2, collections, urlparse, demjson
from urllib import urlencode
import time
import config_utils

from dao.dictsearchstore import *
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebStoreParseResult:
	"""Represents the result of parsing a Chrome Web Store
	search page.
	"""

	def __init__(self):
		self.versionresponse = None
		self.getitemsresponse = []
		self.app_meta = {}
		self.token = None


class WebStoreParser:

	def __init__(self):
		pass

	def parse_getitemsresponse(self, parse_result):
		# Get application id and metadata to put into dict.
		# The key is the app id, the value is the entire metadata chunk.
		for x in parse_result.getitemsresponse[1]:
			parse_result.app_meta[x[0]] = x

		# Get the "token" value to know what our next request index is.
		parse_result.token = parse_result.getitemsresponse[4].split('@')
		logger.info('Got token: %s' % parse_result.token)
		assert len(parse_result.token) == 2

	def parse(self, response):
		parse_result = WebStoreParseResult()
		deserialized_resp = demjson.decode(response.read()[4:])[0]

		parse_result.versionresponse = deserialized_resp[0][1]
		parse_result.getitemsresponse = deserialized_resp[1]
		self.parse_getitemsresponse(parse_result)

		return parse_result


class WebStoreDiscoverer:

	def reset_url_params(self):
		self.url_params = collections.OrderedDict([
			('hl', 'en-US'),
			('gl', 'US'),
			('pv', '20141016'),
			('mce', 'rlb,svp,atf,c3d,ncr,ctm,ac,hot,fcf'),
			('count', '52'),
			('token', ''),
			('category', 'extensions'),
			('searchTerm', ''),
			('sortBy', '0'),
			('container', 'CHROME'),
			('features', '5'),
			('rt', 'j')
		])

	def __init__(self, dict_store, url, db):
		self.alphabets = [ AlphabetType.en_US ]
		self.dict_store = dict_store
		self.crawl_point = url
		self.reset_url_params()
		self.parser = WebStoreParser()
		self.dak = None
		self.db = db

	def __get_next_dak(self, alphabet):
		dak = self.dict_store.get_next(alphabet)
		logger.info('Got: %s' % dak)
		return DictionaryAttackKeyValue.deserialize(dak)

	def __return_dak(self, dak):
		self.dict_store.release(dak)
		logger.info('Returned: %s' % dak.to_value())

	def build_crawl_url(self, dak):
		"""Returns (url, data) for the given dak."""
		self.url_params['searchTerm'] = dak.phrase
		return (self.crawl_point, urlencode(self.url_params))

	def post_request(self, url, data):
		"""Simple wrapper to POST (url, data). Returns response."""
		request = urllib2.Request(url, data, headers=config_utils.HTTP_HEADERS)
		return urllib2.urlopen(request)

	def record_new_app_ids(self, app_meta):
		"""Store the app ids we've crawled into a persistent hash.

		The point of this is to keep track of how many unique
		app ids we've come across.
		"""
		# TODO: Replace with abstracted out AppKeyValueStore
		with self.db.pipeline() as pipe:
			for app_id in app_meta.keys():
				list_name = self.dak.alphabet.name

				# Add app_id with timestamp of when it was
				# discovered. If already exists, it is NOT updated.
				pipe.hsetnx(list_name, app_id, 0)
				logger.info('Queued pipelined put: %s, %s' % (list_name, app_id))

			return pipe.execute()

	def run(self):
		"""Handles delegation of work to crawl the web store for
		app ids and metadata.

		This function will get the next DictionaryAttacKeyValue to use
		to search the Chrome Web Store, and then will return it to the
		queue when it is done.
		"""
		try:
			self.dak = self.__get_next_dak(self.alphabets[0])

			token_r = 0
			while not token_r or token_r < 900:
				url, data = self.build_crawl_url(self.dak)
				response = self.post_request(url, data)

				parse_result = self.parser.parse(response)
				self.record_new_app_ids(parse_result.app_meta)
				self.url_params['token'] = '@'.join(parse_result.token)
				logger.info('Next token: %s' % self.url_params['token'])
				try:
					token_r = int(parse_result.token[1])
				except ValueError:
					logger.info('Possibly reached end of results because could not parse token')
					break
				time.sleep(3)
		finally:
			if self.dak:
				self.reset_url_params()
				self.__return_dak(self.dak)
