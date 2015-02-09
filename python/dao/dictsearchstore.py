from basestore import BaseStore
import redis

from enum import Enum, unique
import logging


logging.basicConfig(level=logging.INFO)


@unique
class AlphabetType(Enum):
	en_US = 1
	ja_JP = 2


class DictionaryAttackKey:
	phrase = ''
	lock = None
	alphabet = None

	def __init__(self, phrase='', lock=None, alphabet=AlphabetType.en_US):
		if not alphabet in list(AlphabetType):
			raise TypeError('Tried to initialize DictionaryAttackKey with invalid AlphabetType: %s' % alphabet)

		self.phrase = phrase
		self.lock = lock
		self.alphabet = alphabet

	def to_list(self):
		return [self.alphabet.name, self.phrase]


class DictionarySearchStore(BaseStore):
	r = None

	def __init__(self, redis_instance):
		self.r = redis_instance

	def get_key(self, key):
		k = ':'.join(key.to_list())
		logging.info('Fetching key: \"%s\"' % k)
		return self.r.get(k)