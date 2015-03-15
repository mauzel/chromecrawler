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


def json_dumps(to_serialize):
	return json.dumps(to_serialize, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))


class ElasticSearchStoreConfiguration(object):

	def __init__(self, es, index, doc_types):
		self.es = es
		self.index = index
		self.doc_types = doc_types


class ReportStore(BaseStore):

	def __init__(self, console=False, out_dir=None, boto=None, es_conf=None):
		self.console = console
		self.out_dir = out_dir
		self.boto = boto
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

		self.es_conf = es_conf

	def es_check_app_id_exists(self, es, index, doc_type, app_id):
		"""Check if a report for this app_id already exists,
		because we need to know if we should create a new
		document, or if we need to update an existing one.
		"""
		try:
			return es.search_exists(
					index=index,
					doc_type=doc_type,
					body={ 'query': { 'term': {'_id': app_id } } }
				)
		except NotFoundError:
			# Bizarre API, why throw an exception
			# in a function that only checks if it exists?
			return False

	def put_to_elasticsearch(self, es_conf, metadata, generated_reports):
		es = es_conf.es
		es_index = es_conf.index
		es_doc_types = es_conf.doc_types
		app_id = metadata['app_id']
		historical_doc_type = es_doc_types['historical']
		current_doc_type = es_doc_types['current']

		if not es_index:
			raise ValueError('es index cannot be: %s' % es_index)

		es_exists = self.es_check_app_id_exists(
			es,
			es_index,
			historical_doc_type,
			app_id
		)

		if not es_exists:
			es_reports = { 'history': [ generated_reports ] }
			es_body = json_dumps(es_reports)
			res = es.index(
				index=es_index,
				doc_type=historical_doc_type,
				id=app_id,
				body=es_body,
				refresh=True
			)
			logger.info('Elasticsearch put result: %s' % res['created'])
		else:
			es_reports = { 'history_update': generated_reports }
			es_format = { 'params': es_reports, 'script': 'ctx._source.history += history_update' }
			es_body = json_dumps(es_format)
			res = es.update(
				index=es_index,
				doc_type=historical_doc_type,
				id=app_id,
				body=es_body,
				refresh=True
			)
			logger.info('Elasticsearch update result: %s' % res)

		current_meta = json_dumps({
				'doc': generated_reports,
				"doc_as_upsert" : True
			})
		res = es.update(
			index=es_index,
			doc_type=current_doc_type,
			id=app_id,
			body=current_meta,
			refresh=True
		)
		logger.info('Elasticsearch update current report result: %s' % res)

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

		if self.es_conf:
			self.put_to_elasticsearch(self.es_conf, metadata, generated_reports)

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