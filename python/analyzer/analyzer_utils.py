#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import json, logging


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
			manifest = json.loads(f.read())
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
			mani = json.loads(f.read())
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
		for p in json_perms:
			if p.startswith('http') or '*' in p:
				continue
			requested_perms.add(p)
		return requested_perms