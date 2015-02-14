import sys
sys.path.append("..")

import collections
import config_utils
from dao.dictsearchstore import *
from redis import WatchError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApplicationIdLocker:
	def __init__(self, db, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.db = db
		self.app_id = None

	def __lock_app_id(self, key, field, value):
		"""Get a simple lock on a specific app_id in Redis."""
		lock_name = ':'.join((self.alphabet.lock_prefix(), field))

		logger.info('Lock name: %s' % lock_name)

		# Check lock. If not locked, get lock.
		lock_result = self.db.set(lock_name, 1, nx=True, ex=3600)
		logger.info('Lock result for key %s: %s' % (key, lock_result))
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

	def stale(self, value):
		"""Checks if the app_id timestamp is 0 (never fetched) or old."""
		return not value

	def set_lock_get_id(self):
		"""Get an app_id that isn't currently locked for fetching."""
		key = self.alphabet.name

		for field, value in self.db.hscan_iter(key, count=20):
			# Check if value is stale
			if not self.stale(value) and self.__lock_app_id(key, field, value):
				logger.info('Got app_id lock: %s', field)
				self.app_id = field
				return field

			logger.info('App_id %s was locked. Trying next...' % field)

		logger.warn('Could not find any unlocked and/or stale app_id!')

	def unlock(self):
		"""Release the lock on an app_id."""
		if not self.app_id:
			return

		lock_name = ':'.join((self.alphabet.lock_prefix(), self.app_id))
		result = self.db.delete(lock_name)
		logger.info('Attempted release of lock: %s (result: %s)' % (lock_name, result))
		return result


class ChromePackageFetcher:

	def reset_url_params(self):
		self.url_params = collections.OrderedDict([
			('response', 'redirect'),
			('x', None), # Do not touch
			('uc', None),
			('id', None),
			('lang', None),
			('prod', 'chrome')
		])

	def __init__(self, url, db, alphabet=AlphabetType.en_US):
		self.alphabet = alphabet
		self.db = db
		self.fetch_point = url
		logger.info('Fetch point: %s' % self.fetch_point)
		self.reset_url_params()
		self.app_id_locker = ApplicationIdLocker(db=db, alphabet=self.alphabet)

	def fetch_app(self, app_id):
		import time
		print 'sleeping for 10 secs to simulate fetching duration'
		time.sleep(10)

	def run(self):
		app_id = None
		try:
			# Get an app_id, add to en_US_processing_set (with TTL)
			# if not already in the set, else get another app_id
			app_id = self.app_id_locker.set_lock_get_id()

			# Fetch data about that app
			self.fetch_app(app_id)

			# Release lock
		finally:
			self.app_id_locker.unlock()