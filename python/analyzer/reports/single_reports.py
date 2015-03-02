#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import json
from abc import ABCMeta, abstractmethod

import config_utils
from dao.reportstore import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseSingleReport(object):
	__metaclass__ = ABCMeta

	@abstractmethod
	def generate_report(self):
		return vars(self)


class ChromePermission:
	"""Represents the 3-ple Chrome permissions as described by
	V. Aravind and M Sethumadhavan.

	Represents:
		chrome.<permission>.<name>
	"""
	def __init__(self, namespace=None, permission=None, name=None):
		self.namespace = namespace
		self.permission = permission
		self.name = name

	def __str__(self):
		return vars(self)

	def __repr__(self):
		return json.dumps(vars(self))

	def __eq__(self, other):
		if isinstance(other, ChromePermission):
			eq_namespace = (self.namespace == other.namespace)
			eq_perm = (self.permission == other.permission)
			eq_name = (self.name == other.name)
			return (eq_namespace and eq_perm and eq_name)
		else:
			return False

	def __ne__(self, other):
		return (not self.__eq__(other))

	def __hash__(self):
		return hash(self.__repr__())


class LeastPrivilegeSingleReport(BaseSingleReport):

	def __init__(self, app_id, web_url=None):
		self.used_permissions = set()
		self.requested_permissions = set()
		self.web_url = web_url
		self.app_id = app_id

	def __str__(self):
		return unicode('LeastPrivilegeSingleReport: %s' % self.app_id)

	def violations(self):
		"""Return the permissions that were requested in the
		app's manifest.json but not actually used in its code.

		In other words, the set difference between requested permissions
		and used permissions.
		"""
		base_used_permissions = set()
		for p in self.used_permissions:
			base_used_permissions.add(p.permission)
		return self.requested_permissions.difference(base_used_permissions)

	def generate_report(self):
		report = super(LeastPrivilegeSingleReport, self).generate_report()
		report['unused_permissions'] = self.violations()
		return report


class MaliciousFlowSingleReport(BaseSingleReport):

	def __init__(self, app_id, web_url=None):
		self.web_url = web_url
		self.app_id = app_id
		self.html_to_remote = set()
		self.remote_to_fs = set()
		self.remote_to_html = set()
		self.requested_permissions = set()

	def __str__(self):
		return unicode('MaliciousFlowSingleReport: %s' % self.app_id)

	def generate_report(self):
		return super(MaliciousFlowSingleReport, self).generate_report()


class JSUnpackAnalyzerSingleReport(BaseSingleReport):

	def __init__(self, app_id, web_url=None):
		self.web_url = web_url
		self.web_url_result = {}
		self.app_id = app_id
		self.results = []
		self.requested_permissions = set()

	def __str__(self):
		return unicode('JSUnpackAnalyzerSingleReport: %s' % self.app_id)

	def generate_report(self):
		return super(JSUnpackAnalyzerSingleReport, self).generate_report()

class WepawetAnalyzerResult(BaseSingleReport):

	def __init__(self, app_id, web_url=None):
		self.web_url = web_url
		self.web_url_result = {}
		self.app_id = app_id

	def __str__(self):
		return unicode('WepawetAnalyzerResult: %s' % self.app_id)

	def generate_report(self):
		return super(WepawetAnalyzerResult, self).generate_report()

