from basestore import BaseStore
import redis, json

from enum import Enum, unique
import logging


logging.basicConfig(level=logging.INFO)


@unique
class AlphabetType(Enum):
	en_US = 1
	ja_JP = 2


class DictionaryAttackKey:
	alphabet = None
	phrase = ''
	locked_at = None
	last_retrieved = None

	def __init__(self, phrase='', locked_at=None, alphabet=AlphabetType.en_US):
		if not alphabet in list(AlphabetType):
			raise TypeError('Tried to initialize DictionaryAttackKey with invalid AlphabetType: %s' % alphabet)

		self.alphabet = alphabet
		self.phrase = phrase
		self.locked_at = locked_at
		self.last_retrieved = None

	def to_list(self):
		return [self.alphabet.name, self.phrase]

	def to_str_key(self):
		return ':'.join(self.to_list())

	def to_value(self):
		return { 'locked_at': self.locked_at, 'last_retrieved': self.last_retrieved }


class DictionarySearchStore(BaseStore):
	r = None

	def __init__(self, redis_instance):
		self.r = redis_instance

	def get_key(self, key):
		k = key.to_str_key()
		logging.info('Fetching key: \"%s\"' % k)
		return json.loads(self.r.get(k))

	def get_any_key(self, alphabet):
		if not alphabet in list(AlphabetType):
			raise TypeError('Invalid AlphabetType: %s' % alphabet)
		raise NotImplementedError

	def release_key(self, key):
		raise NotImplementedError

	def put_key(self, key):
		raise NotImplementedError

	def put_pipelined_keys(self, keys):
		pipe = self.r.pipeline()

		for key in keys:
			str_key = key.to_str_key()
			json_value = json.dumps(key.to_value())
			pipe.set(str_key, json_value)
			logging.info('Queued pipelined put: %s, %s' % (str_key, json_value))

		return pipe.execute()

	def delete_all(self):
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
