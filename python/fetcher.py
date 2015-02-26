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
	app_r = config_utils.redis_from_config(config, key='app_meta_config')

	# Metadata fetcher to be used with the CRX fetcher
	m = MetadataFetcher(base_url=config['detail_page'])

	git_root_dir = config['git_root_dir']
	crx_root_dir = config['crx_root_dir']

	# CRX fetcher, also fetches metadata at the same time
	f = ChromePackageFetcher(url=config['fetch_point'], db=app_r, git_dir=git_root_dir, crx_dir=crx_root_dir, metadata_fetcher=m)

	# Fetch forever
	while True:
		f.run()
		if sleep_time:
			logger.info('Sleeping for: %s seconds' % sleep_time)
			time.sleep(sleep_time)