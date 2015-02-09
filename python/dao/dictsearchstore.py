from basestore import BaseStore
import redis, json

from enum import Enum, unique
import logging


logging.basicConfig(level=logging.INFO)


@unique
class AlphabetType(Enum):
	en_US = 1
	ja_JP = 2

	def processing_name(self):
		"""The name to use for a separate processing list in Redis."""
		return '_'.join((self.name, 'processing'))


class DictionaryAttackKeyValue:
	"""Represent an alphabet, a phrase (or letter), and a timestamp for
	when this key-value was last collected/fetcher.
	"""
	alphabet = None
	phrase = ''
	last_retrieved = None

	def __init__(self, phrase='', last_retrieved=None, alphabet=AlphabetType.en_US):
		"""Initialize this key-value.

		Keyword arguments:
		phrase -- The phrase or letter part of the overall dictionary attack. (default '')
		last_retrieved -- A timestamp representing when this key-value was last collected. (default None)
		alphabet -- An AlphabetType Enum that indicates what language this phrase is from.
		"""
		if not alphabet in list(AlphabetType):
			raise TypeError('Tried to initialize DictionaryAttackKey with invalid AlphabetType: %s' % alphabet)

		self.alphabet = alphabet
		self.phrase = phrase
		self.last_retrieved = None

	def to_value(self):
		"""What this key-value's value looks like."""
		return { 'phrase': self.phrase, 'last_retrieved': self.last_retrieved }


class DictionarySearchStore(BaseStore):
	r = None

	def __init__(self, redis_instance):
		self.r = redis_instance

	def get_next(self, alphabet=AlphabetType.en_US):
		"""Pop the next value from the list of values indicated by the
		alphabet parameter.

		Keyword arguments:
		alphabet -- AlphabetType Enum representing the language that you want to get the next value for.
		"""
		return self.r.rpoplpush(alphabet.name, alphabet.processing_name())

	def release(self, key_value):
		raise NotImplementedError

	def put(self, key_value):
		raise NotImplementedError

	def put_pipelined(self, key_values):
		"""Using pipelining, put all the requested key-values into Redis.

		Return value is the result of the pipeline.
		"""
		pipe = self.r.pipeline()

		for key_value in key_values:
			list_name = key_value.alphabet.name
			json_value = json.dumps(key_value.to_value())
			pipe.rpush(list_name, json_value)
			logging.info('Queued pipelined put: %s, %s' % (list_name, json_value))

		return pipe.execute()

	def delete_all(self):
		"""Delete every single thing from Redis."""
		batch_count = 0
		pipe = self.r.pipeline()
		for key in self.r.scan_iter():
			pipe.delete(key)
			logging.info('Adding for deletion: %s' % key)
			batch_count += 1

			if not batch_count % 10:
				logging.info('Executed pipe.execute(): %s' % pipe.execute())
				batch_count = 0

		if batch_count:
			logging.info('Executed final pipe.execute(): %s' % pipe.execute())
