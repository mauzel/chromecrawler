#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

from itertools import islice
import json
from slimit.lexer import Lexer

import config_utils
from dao.dictsearchstore import *
from dao.reportstore import *
from synchronization.locking import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LeastPrivilegeAnalyzer:
	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.git_dir = git_dir
		self.lock = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.store = ReportStore()

	def __get_app_dir(self, app_id):
		"""Get the extraction path for extracting crx to git repo."""
		return os.path.join(self.git_dir, app_id)

	def __extract_permissions(self, app_dir):
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			manifest = json.loads(f.read())
			if 'permissions' in manifest:
				return manifest['permissions']
			else:
				logger.info('manifest.json does not have permissions')
				return None

	def scan_js(self, js_fn):
		"""V. Aravind and M Sethumadhavan, p.270 describe
		a methodology for detecting if permissions are
		actually used. This is done by scanning JS source
		code for invocations of:

			chrome.<permission>.<name>

		Then comparing the results of this with the permissions
		requested in the manifest.json.
		"""
		used_permissions = set()
		l = Lexer()

		with open(js_fn, 'r') as f:
			l.input(f.read())
			logger.info(js_fn)
			it = l.__iter__()

			for token in l:
				if token.type == 'ID' and token.value.startswith('chrome'):
					permission = None
					name = None
					if it.next().type == 'PERIOD':
						permission = it.next()
					if it.next().type == 'PERIOD':
						name = it.next()
					used_permissions.add('.'.join(filter(None, (token.value, permission.value, name.value))))

		import pprint
		pprint.pprint(used_permissions)
		return used_permissions


	def analyze(self, app_id):
		"""You MUST lock app_id before invoking this function.
		Performs analysis that checks for violation of least privilege
		violation in the given app or extension.

		See V. Aravind and M. Sethumadhavan.
		"""
		app_dir = self.__get_app_dir(app_id)

		if not os.path.exists(app_dir):
			logger.info('Directory does not exist: %s' % app_dir)
			return None

		perms = self.__extract_permissions(app_dir)

		if not perms:
			return None

		results = []

		for root, dirs, files in os.walk(app_dir):
			for f in files:
				if f.endswith('.js'):
					full_path = os.path.join(root, f)
					print full_path
					results.append(self.scan_js(full_path))
		return results

	def run(self):
		app_id = None
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.lock.set_lock_get_id()

			if app_id:
				result = self.analyze(app_id)
				self.store.put(result)


			# Release lock
		finally:
			self.lock.unlock()
