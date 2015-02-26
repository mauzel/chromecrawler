#!/usr/bin/env python
# -*- coding: utf-8 -*-

import redis
import argparse, json, config_utils

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *
from crawler.fetcher import *
from analyzer.single_analyzer import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description='driver for crawling')
parser.add_argument('config', help='path to configuration file')
parser.add_argument('--alphabet', default='en_US', help='alphabet to use, default=en_US')


if __name__ == '__main__':
	args = parser.parse_args()

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	# Get our redis store configurations
	r = config_utils.redis_from_config(config)
	app_r = config_utils.redis_from_config(config, key='app_meta_config')

	git_root_dir = config['git_root_dir']

	# Chained list of analyzers
	analyzers = [
		LeastPrivilegeAnalyzer(git_dir=git_root_dir),
		MaliciousFlowAnalyzer(git_dir=git_root_dir),
		JSUnpackAnalyzer(git_dir=git_root_dir),
		WepawetAnalyzer(git_dir=git_root_dir)
	]

	alphabet = AlphabetType[args.alphabet]

	lock = ApplicationIdLocker(db=app_r, alphabet=alphabet)
	store = ReportStore()

	while True:
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = lock.set_lock_get_id()
			if app_id:
				for analyzer in analyzers:
					result = analyzer.analyze(app_id)
					store.put(result)
			logger.info('done with: %s' % app_id)
		finally:
			lock.unlock()
