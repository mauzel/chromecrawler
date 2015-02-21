import redis
import argparse, json, config_utils

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *
from crawler.fetcher import *


parser = argparse.ArgumentParser(description='driver for testing')
parser.add_argument('config', help='path to configuration file')


if __name__ == '__main__':
	args = parser.parse_args()

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	r = config_utils.redis_from_config(config)
	d = DictionarySearchStore(r)

	#dak = DictionaryAttackKeyValue.deserialize(d.get_next())
	#d.release(dak)
	app_r = config_utils.redis_from_config(config, key='app_meta_config')
	c = WebStoreDiscoverer(d, url=config['crawl_point'], db=app_r)

	m = MetadataFetcher(base_url=config['detail_page'])

	git_root_dir = config['git_root_dir']
	crx_root_dir = config['crx_root_dir']
	f = ChromePackageFetcher(url=config['fetch_point'], db=app_r, git_dir=git_root_dir, crx_dir=crx_root_dir, metadata_fetcher=m)

	for x in xrange(100):
		#c.run()
		f.run()

		import time
		time.sleep(1)