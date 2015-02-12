import redis
import argparse, json, config_utils

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *


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

	c = WebStoreDiscoverer(d)

	while True:
		c.run()