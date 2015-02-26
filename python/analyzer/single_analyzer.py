#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

from itertools import islice
import json
from slimit.lexer import Lexer
from abc import ABCMeta, abstractmethod
from sh import python

import config_utils
from dao.dictsearchstore import *
from dao.reportstore import *
from synchronization.locking import *
from reports.single_reports import *
from analyzer_utils import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseAnalyzer(object):
	__metaclass__ = ABCMeta

	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.git_dir = git_dir
		self.lock = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.store = ReportStore()

	@abstractmethod
	def analyze(self, app_id):
		pass

	@abstractmethod
	def scan_js(self, js_fn, base_app_dir=None):
		pass

	@abstractmethod
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


class LeastPrivilegeAnalyzer(BaseAnalyzer):

	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		super(LeastPrivilegeAnalyzer, self).__init__(db, git_dir, alphabet)

	def scan_js(self, js_fn, base_app_dir=None):
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
		logger.info('LeastPrivilegeAnalyzer: app_id %s' % app_id)

		bootstrap = AnalyzerBootstrap(app_id, self.git_dir)
		if not bootstrap.app_dir:
			return None

		report = LeastPrivilegeSingleReport(app_id)

		if not bootstrap.json_perms:
			return report

		report.requested_permissions.update(bootstrap.perms)
		report.web_url = bootstrap.web_url

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
		super(LeastPrivilegeAnalyzer, self).run()


class MaliciousFlowAnalyzer(BaseAnalyzer):

	sus_perms = [
		'contextMenus', # Allows creation of context menus, which could dl
		'copresence', # Communicate with nearby devices using this service
		'webRequest', # Intercept/block/modify requests
		'blockingWebRequest',
		'declarativeWebRequest', # Intercept/block/modify requests
		'documentScan', # Retrieve images from attached doc scanners
		'downloads', # Programmatically initiate downloads, etc
		'enterprise', # .platformKeys - Get/send certs
		'platformKeys', # Non-enterprise platformKeys
		'fileSystemProvider', # Chrome OS only, create FS
		'gcm', # Send messages using Google Cloud Messaging
		'nativeMessaging', # Has security concerns if used wrongly
		'proxy', # Controls proxies
		'vpnProvider', # Similar risks as proxy
		'pushMessaging', # Deprecated version of gcm
		]

	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		super(MaliciousFlowAnalyzer, self).__init__(db, git_dir, alphabet)

	def scan_js(self, js_fn, base_app_dir=None):
		"""V. Aravind and M Sethumadhavan, p.270-271.
		Unfortunately, this may be outdated. See:
		https://developer.chrome.com/extensions/content_scripts#host-page-communication
		"""
		used_permissions = set()

		# We do not know if Google validates all JS submissions.
		# So use a lexer instead of a parser.
		l = Lexer()

		with open(js_fn, 'r') as f:
			l.input(f.read())
			it = l.__iter__()

			for token in l:
				if token.type == 'ID' and token.value == 'window':
					content = None
					document = None

					# Probably outdated, need to research
					if it.next().type == 'PERIOD':
						content = it.next()
						if content.value != 'content':
							content = None

						if content and it.next().type == 'PERIOD':
							document = it.next()
							if document.value != 'document':
								document = None

					if document:
						print token, content, document

		return used_permissions

	def analyze(self, app_id):
		"""You MUST lock app_id before invoking this function.

		Performs analysis that checks for malicious flows.

		See V. Aravind and M. Sethumadhavan.
		"""
		logger.info('MaliciousFlowAnalyzer: app_id %s' % app_id)

		bootstrap = AnalyzerBootstrap(app_id, self.git_dir)
		if not bootstrap.app_dir:
			return None

		report = MaliciousFlowSingleReport(app_id)

		if not bootstrap.json_perms:
			return report

		report.requested_permissions.update(bootstrap.perms)
		report.web_url = bootstrap.web_url

		# Iterate over every javascript file
		for root, dirs, files in os.walk(bootstrap.app_dir):
			for f in files:
				if f.endswith('.js'):
					full_path = os.path.join(root, f)
					logger.info('Scanning %s' % f)
					used_perms = self.scan_js(full_path)

		return report

	def run(self):
		super(MaliciousFlowAnalyzer, self).run()


class JSUnpackAnalyzer(BaseAnalyzer):
	"""Analyzer that uses the jsunpack-n program to check for
	malicious Javascript and URLs with malicious JavaScript.
	"""

	jsunpack_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../libs/jsunpack_n/'))
	jsunpack_py = os.path.join(jsunpack_dir, 'jsunpackn.py')
	cmd = [
		jsunpack_py,
		'-v', # Verbose
		'-a' # Follow URLs that are found
		]

	def __init__(self, db, git_dir, alphabet=AlphabetType.en_US):
		super(JSUnpackAnalyzer, self).__init__(db, git_dir, alphabet)

	def scan_url(self, url, return_key='web_url'):
		"""Scans an URL for malicious JS using jsunpackn.

		Results are returned as a dict keyed by return_key.
		"""
		result = {}
		result[return_key] = []

		def process_output(line):
			if not line.startswith('\n'):
				result[return_key].append(line)

		os.chdir(self.jsunpack_dir)
		p = python(self.cmd + ['-u', url], _out=process_output)
		p.wait()
		logger.info('Scanned URL: %s' % url)

		return result

	def scan_js(self, js_fn, base_app_dir=''):
		"""Scan a js file using jsunpackn.

		If base_app_dir is provided, it will be used to
		remove that base_app_dir from the front of js_fn,
		i.e. to get a relative path rather than the full path
		of js_fn in the output results.

		Return value is a dict in the form of:
			js_filename: path_to_file,
			analysis: jsunpack_results
		"""
		slice_off = len(base_app_dir) + 1
		if not base_app_dir:
			slice_off = 0

		result = {}
		result['js_fn'] = js_fn[slice_off:]
		result['analysis'] = []

		def process_output(line):
			if not line.startswith('\n'):
				result['analysis'].append(line)

		os.chdir(self.jsunpack_dir)
		p = python(self.cmd + [js_fn], _out=process_output)
		p.wait()

		return result

	def analyze(self, app_id):
		"""You MUST lock app_id before invoking this function.

		Performs analysis that checks for malicious flows.

		See V. Aravind and M. Sethumadhavan.
		"""
		logger.info('JSUnpackAnalyzer: app_id %s' % app_id)

		bootstrap = AnalyzerBootstrap(app_id, self.git_dir)
		if not bootstrap.app_dir:
			return None

		report = JSUnpackAnalyzerSingleReport(app_id)

		if not bootstrap.json_perms:
			return report

		report.requested_permissions.update(bootstrap.perms)
		report.web_url = bootstrap.web_url

		# Iterate over every javascript file
		for root, dirs, files in os.walk(bootstrap.app_dir):
			for f in files:
				if f.endswith('.js'):
					full_path = os.path.join(root, f)
					logger.info('Scanning %s' % f)
					report.results.append(self.scan_js(full_path, bootstrap.app_dir))

		# Perform extra analysis for hosted apps that have a web_url
		if report.web_url:
			report.web_url_result = self.scan_url(report.web_url, return_key=report.web_url)

		return report

	def run(self):
		super(MaliciousFlowAnalyzer, self).run()