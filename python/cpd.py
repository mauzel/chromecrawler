#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, traceback
sys.path.append("..")

from itertools import islice
import json
from sh import java, TimeoutException, nice, ErrorReturnCode_4
import re
import logging, argparse
from elasticsearch import Elasticsearch
from itertools import izip

import config_utils
from dao.reportstore import *


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


parser = argparse.ArgumentParser(description='driver for cpd analysis')
parser.add_argument('config', help='path to configuration file')
parser.add_argument('--source-dir', dest='source_dir', help='directory containing extracted apps, will override anything in the config file')
parser.add_argument('--minimum-tokens', dest='min_tokens', type=int, default=50, help='minimum tokens to use with cpd, default is 50')
parser.add_argument('--format', dest='format', default='csv', help='output format for cpd, default is csv')
parser.add_argument('--es-index', dest='es_index', default='test-index', help='elasticsearch index to use, default is test-index')
parser.add_argument('--es-doc-type', dest='es_doc_type', default='cpd', help='elasticsearch document type name to use, default is cpd')


class CpdCsvResult(object):

	def __init__(self, lines=0, tokens=0, occurrences=0):
		self.lines = lines
		self.tokens = tokens
		self.occurrences = occurrences
		self.files = []

	def __unicode__(self):
		return json.dumps(vars(self), indent=4, sort_keys=True, default=cplaf_default)

	def __str__(self):
		return json.dumps(vars(self), indent=4, sort_keys=True, default=cplaf_default)


def ccr_default(obj):
	if isinstance(obj, CpdCsvResult):
		return vars(obj)
	if isinstance(obj, ChromePermission):
		return unicode(obj.as_triple())
	raise TypeError(type(obj))


def json_dumps(to_serialize):
	try:
		return json.dumps(to_serialize, default=ccr_default, sort_keys=True, indent=4, separators=(',', ': '))
	except UnicodeDecodeError, e:
		logger.error(e)
		return simplejson.dumps(to_serialize, default=ccr_default, sort_keys=True, indent=4, separators=(',', ': '))


class CpdCsvConverter(object):
	LINES = 0
	TOKENS = 1
	OCCURRENCES = 2

	def __init__(self, root_dir):
		self.root_dir = os.path.abspath(root_dir)

	def csv_to_ccr(self, line, app_id, other_id):
		row = line.split(',')
		lines = row[self.LINES]
		tokens = row[self.TOKENS]
		occurrences = row[self.OCCURRENCES]

		result = CpdCsvResult(lines=lines,
			tokens=tokens,
			occurrences=occurrences)

		offset_for_rel = len(self.root_dir) + 1

		lines_and_files = iter(row[3:])

		for line, fn in izip(lines_and_files, lines_and_files):
			try:
				ln = int(line)

				result.files.append({ 'file': fn[offset_for_rel:], 'line': ln })

			except ValueError, e:
				logger.error('%s,%s' % (line, fn))
				logger.exception(','.join(lines_and_files))

		return result


class CpdRunner(object):

	CMD = 'java'
	NICE = '-15'
	JVM_MEM = '-Xmx512m'
	JV_CP_ARG = '-cp'
	CPD_CLASS_NAME = 'net.sourceforge.pmd.cpd.CPD'
	CPD_FILES_ARG = '--files'
	CPD_LANG_ARG = '--language'
	CPD_MIN_TOKENS_ARG = '--minimum-tokens'
	CPD_FORMAT_ARG = '--format'

	def __init__(self, jvm_cp, min_tokens=50, lang='ecmascript', cpd_format='text'):
		self.cmd = [self.NICE, self.CMD, self.JVM_MEM, self.JV_CP_ARG, jvm_cp, self.CPD_CLASS_NAME]
		self.min_tokens = unicode(min_tokens)
		self.lang = lang
		self.format = cpd_format

	def _construct_cmd(self, dir_a, dir_b):
		return self.cmd + [self.CPD_MIN_TOKENS_ARG, self.min_tokens, self.CPD_LANG_ARG, self.lang, self.CPD_FORMAT_ARG, self.format, self.CPD_FILES_ARG, dir_a, self.CPD_FILES_ARG, dir_b]

	def run_cpd(self, src_dir, compare_dir):
		result = []
		def process_output(line):
			if self.format.lower() == 'csv':
				if line and not line == 'lines,tokens,occurrences\n':
					result.append(line.rstrip('\n'))
			else:
				result.append(line)

		try:
			constructed_cmd = self._construct_cmd(src_dir, compare_dir)
			logger.info('Running: %s' % constructed_cmd)
			p = nice(constructed_cmd,
					_out=process_output,
					_timeout=560)
			p.wait()
		except ErrorReturnCode_4, e:
			# Why... does CPD exit with exit status 4 when nothing goes wrong.
			logger.info('Compared: \'%s\' with \'%s\'' % (src_dir, compare_dir))
		except TimeoutException, e:
			logger.error('Took way too long to run cpd: \'%s\' on \'%s\'.' % (src_dir, compare_dir), e)
		return result


def es_check_app_id_exists(es, index, doc_type, app_id):
	"""Check if a doc for this app_id already exists,
	because we need to know if we should create a new
	document, or if we need to update an existing one.
	"""
	try:
		return es.search_exists(
				index=index,
				doc_type=doc_type,
				body={ 'query': { 'term': {'_id': app_id } } }
			)
	except NotFoundError:
		# Bizarre API, why throw an exception
		# in a function that only checks if it exists?
		return False


def put_to_es(es, es_index, doc_type, app_id, cpd_analysis):
	es_exists = es_check_app_id_exists(
		es,
		es_index,
		doc_type,
		app_id
	)

	if not es_exists:
		es_reports = { 'cpd_results': [ cpd_analysis ] }
		es_body = json_dumps(es_reports)
		res = es.index(
			index=es_index,
			doc_type=doc_type,
			id=app_id,
			body=es_body,
			refresh=True
		)
		logger.info('Elasticsearch put result: %s' % res['created'])
	else:
		es_reports = { 'cpd_results_update': cpd_analysis }
		es_format = { 'params': es_reports, 'script': 'ctx._source.cpd_results += cpd_results_update' }
		es_body = json_dumps(es_format)
		res = es.update(
			index=es_index,
			doc_type=doc_type,
			id=app_id,
			body=es_body,
			refresh=True
		)
		logger.info('Elasticsearch update result: %s' % res)


if __name__ == '__main__':
	args = parser.parse_args()

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	git_root_dir = config['git_root_dir']
	reports_root_dir = config['reports_root_dir']

	if args.source_dir:
		git_root_dir = args.source_dir

	java_classpath = ':/home/sena/temp/pmd-bin-5.2.3/lib/asm-5.0.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/commons-io-2.4.jar:/home/sena/temp/pmd-bin-5.2.3/lib/commons-lang3-3.3.2.jar:/home/sena/temp/pmd-bin-5.2.3/lib/javacc-5.0.jar:/home/sena/temp/pmd-bin-5.2.3/lib/jaxen-1.1.4.jar:/home/sena/temp/pmd-bin-5.2.3/lib/jcommander-1.35.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-core-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-cpp-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-cs-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-fortran-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-go-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-java-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-javascript-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-jsp-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-php-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-plsql-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-ruby-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-vm-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/pmd-xml-5.2.3.jar:/home/sena/temp/pmd-bin-5.2.3/lib/rhino-1.7R4.jar:/home/sena/temp/pmd-bin-5.2.3/lib/saxon-9.1.0.8-dom.jar:/home/sena/temp/pmd-bin-5.2.3/lib/saxon-9.1.0.8.jar:/home/sena/temp/pmd-bin-5.2.3/lib/xercesImpl-2.11.0.jar:/home/sena/temp/pmd-bin-5.2.3/lib/xml-apis-1.4.01.jar'

	cpd = CpdRunner(jvm_cp=java_classpath, min_tokens=args.min_tokens, cpd_format=args.format)

	app_ids = os.listdir(git_root_dir)
	immutable_ids = tuple(app_ids)
	ccc = CpdCsvConverter(root_dir=git_root_dir)

	es_index = args.es_index
	es_doc_type = args.es_doc_type
	es = Elasticsearch()

	# Need to O(n^2) this---compare each app with every other app
	# We could save some time if we are smart and use more memory,
	# but our input size isn't large enough to care.
	for app_id in immutable_ids:
		abs_path = os.path.join(git_root_dir, app_id)

		for other_id in app_ids:
			if other_id == app_id:
				logger.info('Skipping comparing with self')
				continue
			other_abs_path = os.path.join(git_root_dir, other_id)
			result = cpd.run_cpd(abs_path, other_abs_path)

			results = []
			for line in result:
				if line:
					ccr = ccc.csv_to_ccr(line, app_id, other_id)
					if ccr:
						results.append(ccr)
			if results:
				final_result = {}
				final_result['app_id'] = app_id
				final_result['other_app_id'] = other_id
				final_result['minimum_tokens'] = args.min_tokens
				final_result['results'] = results
				final_result['timestamp'] = config_utils.current_time_millis()
				
				put_to_es(es, es_index, es_doc_type, app_id, final_result)

			break
			
		break


