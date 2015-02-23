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
from reports.single_reports import *
from analyzer_utils import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LeastPrivilegeAnalyzer:
	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.git_dir = git_dir
		self.lock = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.store = ReportStore()

	def scan_js(self, js_fn):
		"""V. Aravind and M Sethumadhavan, p.270 describe
		a methodology for detecting if permissions are
		actually used. This is done by scanning JS source
		code for invocations of:

			chrome.<permission>.<name>

		Which we put into the set that is returned by this function.

		LATER (i.e. not in this function), we compare the results 
		of this with the permissions requested in the manifest.json.
		"""
		used_permissions = set()

		# We do not know if Google validates all JS submissions.
		# So use a lexer instead of a parser.
		l = Lexer()

		with open(js_fn, 'r') as f:
			l.input(f.read())
			it = l.__iter__()

			for token in l:
				if token.type == 'ID' and token.value == 'chrome':
					permission = None
					name = None

					# Need a sliding window to get the rest of the
					# permission 3-ple
					if it.next().type == 'PERIOD':
						permission = it.next()
					if it.next().type == 'PERIOD':
						name = it.next()

					new_perm = ChromePermission()

					if token:
						new_perm.namespace = token.value
					if permission:
						new_perm.permission = permission.value
					if name:
						new_perm.name = name.value

					used_permissions.add(new_perm)

		return used_permissions

	def analyze(self, app_id):
		"""You MUST lock app_id before invoking this function.

		Performs analysis that checks for violation of least privilege
		violation in the given app or extension.

		See V. Aravind and M. Sethumadhavan.
		"""
		logger.info('app_id %s' % app_id)
		bootstrap = AnalyzerBootstrap(app_id, self.git_dir)

		if not bootstrap.app_dir:
			return None

		report = LeastPrivilegeSingleReport(app_id)

		if not bootstrap.json_perms:
			return report

		report.requested_permissions.update(bootstrap.perms)

		# Iterate over every javascript file
		for root, dirs, files in os.walk(bootstrap.app_dir):
			for f in files:
				if f.endswith('.js'):
					full_path = os.path.join(root, f)
					logger.info('Scanning %s' % f)
					used_perms = self.scan_js(full_path)
					report.used_permissions.update(used_perms)

		return report

	def run(self):
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.lock.set_lock_get_id()

			if app_id:
				result = self.analyze(app_id)
				self.store.put(result)
		finally:
			self.lock.unlock()
