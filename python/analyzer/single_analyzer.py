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
		"""Get the permissions part of the manifest.json in app_dir as
		a Python dictionary.
		"""
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			manifest = json.loads(f.read())
			if 'permissions' in manifest:
				return manifest['permissions']
			else:
				logger.info('manifest.json does not have permissions')
				return None

	def find_web_url(self, app_dir):
		"""Checks for the 'web_url' property in the manifest.json
		file. The presence of this property indicates whether the
		given app is a hosted app or not.

		A hosted app is basically a web app hosted by the app creator,
		and is basically telling the Chrome app to run the person's web
		app within your browser.
		"""
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			mani = json.loads(f.read())
			if 'app' in mani and 'launch' in mani['app']:
				launch = mani['app']['launch']
				if 'web_url' in launch:
					logger.info('manifest.json web_url: %s' % launch['web_url'])
					return launch['web_url']

		logger.info('manifest.json does not have web_url')
		return None

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

	def json_perms_to_set(self, json_perms):
		requested_perms = set()
		for p in json_perms:
			if p.startswith('http') or '*' in p:
				continue
			requested_perms.add(p)
		return requested_perms


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

		logger.info('app_id %s' % app_id)

		report = LeastPrivilegeSingleReport(app_id)

		# Check for web_url, which indicates if hosted app or not
		report.web_url = self.find_web_url(app_dir)

		json_perms = self.__extract_permissions(app_dir)
		if not json_perms:
			return report

		perms = self.json_perms_to_set(json_perms)

		report.requested_permissions.update(perms)

		# Iterate over every javascript file
		for root, dirs, files in os.walk(app_dir):
			for f in files:
				if f.endswith('.js'):
					full_path = os.path.join(root, f)
					logger.info('Scanning %s' % f)
					used_perms = self.scan_js(full_path)
					report.used_permissions.update(used_perms)

		return report

	def run(self, test=False, app_id=None):
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			if not test:
				app_id = self.lock.set_lock_get_id()

			if app_id:
				result = self.analyze(app_id)
				self.store.put(result)
		finally:
			if not test:
				# Release lock
				self.lock.unlock()
