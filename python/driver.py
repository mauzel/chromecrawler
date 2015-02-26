import redis
import argparse, json, config_utils

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *
from crawler.fetcher import *
from analyzer.single_analyzer import *


parser = argparse.ArgumentParser(description='driver for testing')
parser.add_argument('config', help='path to configuration file')


if __name__ == '__main__':
	args = parser.parse_args()

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	# Get our redis store configurations
	r = config_utils.redis_from_config(config)
	d = DictionarySearchStore(r)
	app_r = config_utils.redis_from_config(config, key='app_meta_config')

	# Crawler
	c = WebStoreDiscoverer(d, url=config['crawl_point'], db=app_r)

	# Metadata fetcher to be used with the CRX fetcher
	m = MetadataFetcher(base_url=config['detail_page'])

	git_root_dir = config['git_root_dir']
	crx_root_dir = config['crx_root_dir']

	# CRX fetcher, also fetches metadata at the same time
	f = ChromePackageFetcher(url=config['fetch_point'], db=app_r, git_dir=git_root_dir, crx_dir=crx_root_dir, metadata_fetcher=m)

	# Test crawling and fetching
	#for x in xrange(100):
		#c.run()
		#f.run()

		#import time
		#time.sleep(3)

	# Single report analyzers
	lpa = LeastPrivilegeAnalyzer(db=app_r, git_dir=git_root_dir)
	print lpa.analyze('aecmbngpoblfijikbmeeehekhmelghgi').violations()

	mfa = MaliciousFlowAnalyzer(db=app_r, git_dir=git_root_dir)
	print mfa.analyze('jcnibiamknmoengmomlfnjneiemlpnlf')

	jsua = JSUnpackAnalyzer(db=app_r, git_dir=git_root_dir)
	jsua_result = jsua.analyze('aecmbngpoblfijikbmeeehekhmelghgi')

	import pprint
	pprint.pprint(jsua_result.results)
	print
	pprint.pprint(jsua_result.web_url_result)

	wa = WepawetAnalyzer(db=app_r, git_dir=git_root_dir)
	wa_result = wa.analyze('anaphblkfplenhkephgneolhnmjminjg')

	import pprint
	pprint.pprint(wa_result.web_url_result)

	#for x in xrange(100):
		#print mfa.run()
		#import time
		#time.sleep(0.5)