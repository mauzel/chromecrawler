#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import simplejson, logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyzerUtils:

	def __init__(self):
		pass

	@staticmethod
	def extract_permissions(app_dir):
		"""Get the permissions part of the manifest.json in app_dir as
		a Python dictionary.
		"""
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			manifest = simplejson.loads(f.read(), strict=False)
			if 'permissions' in manifest:
				return manifest['permissions']
			else:
				logger.info('manifest.json does not have permissions')
				return None

	@staticmethod
	def find_web_url(app_dir):
		"""Checks for the 'web_url' property in the manifest.json
		file. The presence of this property indicates whether the
		given app is a hosted app or not.

		A hosted app is basically a web app hosted by the app creator,
		and is basically telling the Chrome app to run the person's web
		app within your browser.
		"""
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			mani = {}
			try:
				file_contents = f.read()
				mani = simplejson.loads(file_contents, strict=False)
			except ValueError, e:
				logger.exception('Failed to read JSON from %s' % app_dir)

			if 'app' in mani and 'launch' in mani['app']:
				launch = mani['app']['launch']
				if 'web_url' in launch:
					logger.info('manifest.json web_url: %s' % launch['web_url'])
					return launch['web_url']

		logger.info('manifest.json does not have web_url')
		return None

	@staticmethod
	def json_perms_to_set(json_perms):
		requested_perms = set()
		if json_perms:
			for p in json_perms:
				if isinstance(p, dict):
					p = p.iterkeys().next()
				elif p.startswith('http') or '*' in p:
					continue
				requested_perms.add(p)
		return requested_perms


class AnalyzerBootstrap:

	def __init__(self, app_id, git_dir):
		self.git_dir = git_dir
		self.app_id = app_id

		self.app_dir = os.path.join(git_dir, app_id)

		if not os.path.exists(self.app_dir):
			logger.info('Directory does not exist: %s' % self.app_dir)
			self.app_dir = None
			return

		# Check for web_url, which indicates if hosted app or not
		self.web_url = AnalyzerUtils.find_web_url(self.app_dir)
		self.json_perms = AnalyzerUtils.extract_permissions(self.app_dir)
		self.perms = AnalyzerUtils.json_perms_to_set(self.json_perms)