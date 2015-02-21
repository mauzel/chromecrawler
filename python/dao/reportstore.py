#!/usr/bin/env python
# -*- coding: utf-8 -*-

from basestore import BaseStore
import redis, json
import config_utils

from enum import Enum, unique
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReportStore(BaseStore):
	r = None

	def __init__(self):
		pass

	def put(self, report):
		logger.info('Put report: %s' % report)