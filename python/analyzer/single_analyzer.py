#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

import json

import config_utils
from dao.dictsearchstore import *
from synchronization.locking import *

class LeastPrivilegeAnalyzer:
	def __init__(self, git_dir, alphabet=AlphabetType.en_US):
		self.git_dir = git_dir
		self.lock = ApplicationIdLocker(db=db, alphabet=self.alphabet)
		self.alphabet = alphabet

	def get_app_dir(self, app_id):
		"""Get the extraction path for extracting crx to git repo."""
		return os.path.join(self.git_dir, app_id)

	def extract_permissions(self, app_dir):
		with open(os.path.join(app_dir, 'manifest.json'), 'r') as f:
			manifest = json.loads(f)
			return manifest['permissions']

	def analyze(self, app_id):
		"""You MUST lock app_id before invoking this function.
		Performs analysis that checks for violation of least privilege
		violation in the given app or extension.

		See V. Aravind and M. Sethumadhavan.
		"""
		app_dir = self.get_app_dir(app_id)
		perms = self.extract_permissions(app_dir)

	def run(self):
		app_id = None
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.lock.set_lock_get_id()

			if app_id:
				self.analyze(app_id)

			# Release lock
		finally:
			self.lock.unlock()
