#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('..')

import os
import redis, json
from enum import Enum, unique
import logging

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

	def __init__(self, console=False, out_dir=None, boto=None):
		self.console = console
		self.out_dir = out_dir
		self.boto = boto
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

	def put(self, reports, metadata):
		if not 'app_id' in metadata or not 'version' in metadata:
			raise KeyError('metadata is missing app_id or version, so cannot put report: %s' % unicode(metadata))
		generated_reports = []

		for report in reports:
			generated_reports.append({ report.report_type: report.generate_report() })

		json_reports = json.dumps(generated_reports, default=set_default, sort_keys=True, indent=4, separators=(',', ': '))

		# Put to S3 or something
		if self.boto:
			raise NotImplementedError('Putting reports to S3 not implemented yet')

		if self.console:
			print json_reports

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