import sys
sys.path.append("..")

import urllib2, collections, urlparse, demjson
from urllib import urlencode

from dao.dictsearchstore import *
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


HTTP_HEADERS = {
	'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	'accept-encoding': '',
	'accept-language': 'en-US,en;q=0.8,ja;q=0.6,ko;q=0.4',
	'dnt': '1',
	'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.93 Safari/537.36',
	'x-same-domain': '1',
	'origin': 'https://chrome.google.com',
	'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
	'referer': 'https://chrome.google.com/webstore/search/a?_feature=free&_category=apps',
	'dnt': '1',
	'data': 'login=&'
}

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
		assert len(parse_result.token) == 2

	def parse(self, response):
		parse_result = WebStoreParseResult()
		deserialized_resp = demjson.decode(response.read()[4:])[0]

		parse_result.versionresponse = deserialized_resp[0][1]
		parse_result.getitemsresponse = deserialized_resp[1]
		self.parse_getitemsresponse(parse_result)

		return parse_result


class WebStoreDiscoverer:

	def __init__(self, dict_store, url):
		self.alphabets = [ AlphabetType.en_US ]
		self.dict_store = dict_store
		self.crawl_point = url
		logger.info('Crawl point: %s' % self.crawl_point)
		self.url_params = collections.OrderedDict([
			('hl', 'en-US'),
			('gl', 'US'),
			('pv', '20141016'),
			('mce', 'rlb,svp,atf,c3d,ncr,ctm,ac,hot,fcf'),
			('count', '5'),
			('token', ''),
			('category', 'apps'),
			('searchTerm', ''),
			('sortBy', '0'),
			('container', 'CHROME'),
			('features', '5'),
			('rt', 'j')
		])
		self.parser = WebStoreParser()
		self.dak = None

	def __get_next_dak(self, alphabet):
		dak = self.dict_store.get_next(alphabet)
		logger.info('Got: %s' % dak)
		return DictionaryAttackKeyValue.deserialize(dak)

	def __return_dak(self, dak):
		self.dict_store.release(dak)
		logger.info('Returned: %s' % dak.to_value())

	def build_crawl_url(self, dak):
		self.url_params['searchTerm'] = dak.phrase
		return (self.crawl_point, urlencode(self.url_params))

	def post_request(self, url, data):
		request = urllib2.Request(url, data, headers=HTTP_HEADERS)
		return urllib2.urlopen(request)

	def store_all_app_meta(self, app_meta):
		pass

	def fetch_app_packages(self, app_meta):
		pass

	def run(self):
		self.dak = self.__get_next_dak(self.alphabets[0])
		url, data = self.build_crawl_url(self.dak)
		response = self.post_request(url, data)

		parse_result = self.parser.parse(response)
		self.store_all_app_meta(parse_result.app_meta)
		self.fetch_app_packages(parse_result.app_meta)


		if self.dak:
			self.__return_dak(self.dak)
