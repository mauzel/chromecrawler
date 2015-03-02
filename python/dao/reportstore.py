#!/usr/bin/env python
# -*- coding: utf-8 -*-

from basestore import BaseStore
import os
import redis, json
import config_utils

from enum import Enum, unique
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def set_default(obj):
	if isinstance(obj, set):
		return list(obj)
	raise TypeError


class ReportStore(BaseStore):

	def __init__(self, console=False, out_dir=None, boto=None):
		self.console = console
		self.out_dir = out_dir
		self.boto = boto
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

	def put(self, report, metadata):
		if not 'app_id' in metadata or not 'version' in metadata:
			raise KeyError('metadata is missing app_id or version, so cannot put report: %s' % unicode(metadata))

		generated_report = report.generate_report()
		json_report = json.dumps(generated_report, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))

		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')
		if self.console:
			print json_report
		if self.out_dir and 'version' in metadata:
			out_path = os.path.join(self.out_dir, metadata['app_id'])
			out_path = os.path.join(out_path, metadata['version'] + '.json')
			with open(out_path, 'wb') as f:
				f.write(json_report)
		logger.info('Put report: %s' % report)