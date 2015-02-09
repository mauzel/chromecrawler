from abc import ABCMeta, abstractmethod

class BaseStore(object):
	__metaclass__ = ABCMeta

	@abstractmethod
	def get_key(self, key):
		pass