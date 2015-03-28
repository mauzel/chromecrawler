#!/usr/bin/env python
# -*- coding: utf-8 -*-

import redis
import argparse, json, config_utils
import time
from elasticsearch import Elasticsearch

from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue
from crawler.discoverer import *
from crawler.fetcher import *
from analyzer.single_analyzer import *
from analyzer.reports.single_reports import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description='driver for crawling')
parser.add_argument('config', help='path to configuration file')
parser.add_argument('--sleep', default=1, type=float, help='time to sleep in seconds in between dictionary attack keys, default=1')
parser.add_argument('--alphabet', default='en_US', help='alphabet to use, default=en_US')


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

	git_root_dir = config['git_root_dir']
	crx_root_dir = config['crx_root_dir']
	reports_root_dir = config['reports_root_dir']

	# Discovering (Crawling) happens separately

	# Instantiate metadata fetcher, which gets passed into fetcher
	m = MetadataFetcher(base_url=config['detail_page'])

	# CRX fetcher, also fetches metadata at the same time
	f = ChromePackageFetcher(url=config['fetch_point'],
							 db=app_r,
							 git_dir=git_root_dir,
							 crx_dir=crx_root_dir,
							 metadata_fetcher=m)

	# Chained list of analyzers
	analyzers = [
		LeastPrivilegeAnalyzer(git_dir=git_root_dir),
		#MaliciousFlowAnalyzer(git_dir=git_root_dir),
		JSUnpackAnalyzer(git_dir=git_root_dir),
		WepawetAnalyzer(git_dir=git_root_dir)
	]

	alphabet = AlphabetType[args.alphabet]

	# Elasticsearch report settings to use in the ReportStore
	es_conf = ElasticSearchStoreConfiguration(
		es=Elasticsearch(),
		index='test-index',
		doc_types={
			'historical': 'historical',
			'current': 'current'
		}
	)

	lock = ApplicationIdLocker(db=app_r, alphabet=alphabet)
	store = ReportStore(console=False, out_dir=reports_root_dir, es_conf=es_conf)

	while True:
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = lock.set_lock_get_id()
			if app_id:
				# Fetch app and fetch metadata for the app
				metadata = f.run(app_id)

				if metadata:
					reports = { metadata.__type__: metadata }
					for analyzer in analyzers:
						report_name = analyzer.__class__.__name__
						try:
							reports[report_name] = analyzer.analyze(app_id)
						except TypeError, e:
							logger.exception('TypeError during analyzing, possible issue is due to regex parsing failure in the slimit lexer')
							reports[report_name] = FailureReport(report_type=report_name, message=unicode(e))
						except UnicodeDecodeError, e:
							logger.exception('UnicodeDecodeError during analyzing, possibly due to incorrectly encoded JSON')
							reports[report_name] = FailureReport(report_type=report_name, message=unicode(e))

					store.put(reports, vars(metadata))

			logger.info('done with: %s' % app_id)
			import time
			time.sleep(3)
		finally:
			lock.unlock()
