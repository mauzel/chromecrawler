import sys
sys.path.append("..")

from dao.dictsearchstore import *
import logging


logging.basicConfig(level=logging.INFO)


class WebStoreDiscoverer:

	alphabets = []
	dict_store = None

	def __init__(self, dict_store):
		self.alphabets = [ AlphabetType.en_US ]
		self.dict_store = dict_store

	def __get_next_dak(self, alphabet):
		dak = self.dict_store.get_next(alphabet)
		logging.info('Got: %s' % dak)
		return DictionaryAttackKeyValue.deserialize(dak)

	def __return_dak(self, dak):
			self.dict_store.release(dak)
			logging.info('Returned: %s' % dak)

	def run(self):
		dak = self.__get_next_dak(self.alphabets[0])

		if dak:
			self.__return_dak(dak)
