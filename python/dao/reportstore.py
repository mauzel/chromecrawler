#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('..')

import os
import redis, json
from enum import Enum, unique
import logging
from elasticsearch.exceptions import NotFoundError

from basestore import BaseStore
from analyzer.reports.single_reports import *
import config_utils


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def set_default(obj):
	if isinstance(obj, set):
		return list(obj)
	if isinstance(obj, ChromePermission):
		return unicode(obj.as_triple())
	raise TypeError(type(obj))


class ReportStore(BaseStore):

	def __init__(self, console=False, out_dir=None, boto=None, es=None, es_index=None, es_doc_type='app-report'):
		self.console = console
		self.out_dir = out_dir
		self.boto = boto
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

		if es and not es_index:
			raise ValueError('No Elasticsearch index provided even though ES was provided')

		self.es = es
		self.es_index = es_index
		self.es_doc_type = es_doc_type

	def put(self, reports, metadata):
		if not 'app_id' in metadata or not 'version' in metadata:
			raise KeyError('metadata is missing app_id or version, so cannot put report: %s' % unicode(metadata))

		generated_reports = {}

		for key in reports:
			try:
				report = reports[key]
				generated_reports[key] = report.generate_report()
			except AttributeError:
				if isinstance(report, basestring):
					continue
				else:
					logger.exception('Got a non-string report without generate_report()')

		json_reports = json.dumps(generated_reports, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))

		# Put to S3 or something
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

		if self.console:
			print json_reports

		if self.es:
			try:
				es_exists = self.es.search_exists(
						index=self.es_index,
						doc_type=self.es_doc_type,
						body={ 'query': { 'term': {'_id': metadata['app_id'] } } }
					)
			except NotFoundError:
				es_exists = False

			if not es_exists:
				es_reports = { 'history': [generated_reports] }
				es_body = json.dumps(es_reports, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))
				res = self.es.index(
					index=self.es_index,
					doc_type=self.es_doc_type,
					id=metadata['app_id'],
					body=es_body,
					refresh=True
				)
				logger.info('Elasticsearch put result: %s' % res['created'])
			else:
				es_reports = { 'history_update': generated_reports }
				es_format = { 'params': es_reports, 'script': 'ctx._source.history += history_update' }
				es_body = json.dumps(es_format, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))
				res = self.es.update(
					index=self.es_index,
					doc_type=self.es_doc_type,
					id=metadata['app_id'],
					body=es_body,
					refresh=True
					)
				logger.info('Elasticsearch update result: %s' % res)

		# If output directory is supplied, save report to local disk
		if self.out_dir and 'version' in metadata:
			# Locate output directory for reports, make directories if needed
			out_path = os.path.join(self.out_dir, metadata['app_id']) + os.sep
			if not os.path.exists(os.path.dirname(out_path)):
				os.makedirs(os.path.dirname(out_path))

			# Append report's filename (<version>.json) to the path
			out_path = os.path.join(out_path, metadata['version'] + '.json')

			with open(out_path, 'wb') as f:
				f.write(json_reports)
				logger.info('Wrote report to disk: %s' % out_path)