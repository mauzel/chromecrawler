#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod

class BaseStore(object):
	__metaclass__ = ABCMeta

	@abstractmethod
	def put(self, key_value):
		pass