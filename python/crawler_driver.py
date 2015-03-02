#!/usr/bin/env python
# -*- coding: utf-8 -*-

import redis
import argparse, json, config_utils
import time

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *
from crawler.fetcher import *
from analyzer.single_analyzer import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description='driver for crawling')
parser.add_argument('config', help='path to configuration file')
parser.add_argument('--sleep', default=1, type=float, help='time to sleep in seconds in between dictionary attack keys, default=1')


if __name__ == '__main__':
	args = parser.parse_args()
	sleep_time = args.sleep

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	# Get our redis store configurations
	r = config_utils.redis_from_config(config)
	d = DictionarySearchStore(r)
	app_r = config_utils.redis_from_config(config, key='app_meta_config')

	# Crawler
	c = WebStoreDiscoverer(d, url=config['crawl_point'], db=app_r)

	# Crawl forever
	while True:
		c.run()
		if sleep_time:
			logger.info('Sleeping for: %s seconds' % sleep_time)
			time.sleep(sleep_time)