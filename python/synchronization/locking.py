#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

from redis import WatchError

import config_utils
from dao.dictsearchstore import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ApplicationIdLocker(object):
	"""Handles locking/unlocking of app_ids so that multiple
	fetchers don't fetch the same app_id.

	Invokers want to use:
		- set_lock_get_id()
		- unlock()

	You definitely want to put unlock() in a finally.
	"""

	def __init__(self, db, alphabet=AlphabetType.en_US, ttl=3600):
		self.alphabet = alphabet
		self.db = db
		self.app_id = None
		self.ttl = ttl

	def __lock_app_id(self, key, field, value):
		"""Get a simple lock on a specific app_id in Redis."""
		lock_name = ':'.join((self.alphabet.lock_prefix(), field))

		logger.info('Lock name: %s' % lock_name)

		# Check lock. If not locked, get lock.
		lock_result = self.db.set(lock_name, 1, nx=True, ex=self.ttl)
		logger.debug('Lock result for key %s: %s' % (key, lock_result))
		if not lock_result:
			return False

		try:
			with self.db.pipeline() as pipe:
				pipe.watch(lock_name)
				pipe.multi()
				pipe.hset(key, field, config_utils.current_time_millis())
				pipe.execute()
				return True
		except WatchError:
				return False

	def need_fetch(self, value):
		"""Checks if the app_id timestamp is 0 (never fetched) or old."""
		value = int(value)
		return value == 0 or value < config_utils.current_time_millis() - 604800000

	def set_lock_get_id(self):
		"""Get an app_id that isn't currently locked for fetching."""
		key = self.alphabet.name

		for field, value in self.db.hscan_iter(key, count=20):
			# Check if value is stale
			if self.need_fetch(value) and self.__lock_app_id(key, field, value):
				logger.info('Got app_id lock: %s', field)
				self.app_id = field
				return field

			logger.debug('App_id %s was locked. Trying next...' % field)

		logger.warn('Could not find any unlocked and/or stale app_id!')

	def unlock(self):
		"""Release the lock on an app_id."""
		if not self.app_id:
			return

		lock_name = ':'.join((self.alphabet.lock_prefix(), self.app_id))
		result = self.db.delete(lock_name)
		logger.info('Attempted release of lock: %s (result: %s)' % (lock_name, result))
		return result