#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import json

import config_utils
from dao.reportstore import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


class LeastPrivilegeSingleReport:

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

