from elasticsearch import Elasticsearch
import json
from pprint import pprint
from operator import itemgetter
import math

class ElasticSearchStatAnalyzer:

	def __init__(self):
		self.def_index = "test-index"
		self.type_current = "current"
		self.type_historical = "historical"
		self.search_granularity = 100
		self.app_ids=[]
		self.es = Elasticsearch()
		res = self.es.search(index = self.def_index, doc_type = self.type_current, size=self.search_granularity)#, body = {"query": {"match_all": {}}})
		self.app_count = res['hits']['total']

		for hit in res['hits']['hits']:
			self.app_ids.append(hit['_id'])
		self.find_total_apps()	

	def find_total_apps(self):
		res = self.es.search(index = self.def_index, doc_type = self.type_current, body = {"query": {"match_all": {}}})
		self.total_apps = res['hits']['total']	

	
	def correlate_rating_unused_perm(self):
		
		rating_unused_perm_histogram={'0': '0', '0.5': '0', '1.0': '0', '1.5': '0', '2.0': '0', '2.5': '0', '3.0': '0', '3.5': '0', '4.0':'0', '4.5':'0', '5.0':'0'}

		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id=app_id)
			round_up = 0.5 * math.ceil(2 * res['_source']['AppMetadata']['rating_value'])
			try:
				if not res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']:
					continue
				else:
					print res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']
					rating_unused_perm_histogram[str(round_up)] = int(rating_unused_perm_histogram[str(round_up)]) + 1
			except KeyError:
				print "KeyError"
			

		print rating_unused_perm_histogram	

	def count_privilege_violations(self):
		unused_privilege_count={}
		
		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id=app_id)
			try:
				if not res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']:
					continue
				else:
					cur_violations = res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']
					for violation in cur_violations:
						if violation in unused_privilege_count:
							unused_privilege_count[violation] = unused_privilege_count[violation] + 1
						else:
							unused_privilege_count[violation] = 1
			except KeyError:
				print "KeyError"

		print unused_privilege_count
		return
	
	def top_rated_applications(self, min_downloads, max_downloads):
		app_id_ratings={}

		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id=app_id)
			if(res['_source']['AppMetadata']['downloads']):
				if int(res['_source']['AppMetadata']['downloads']) >= min_downloads and int(res['_source']['AppMetadata']['downloads']) < max_downloads:
					app_id_ratings[app_id] = float(res['_source']['AppMetadata']['rating_value'])
			else:
				continue

		print app_id_ratings

if __name__ == "__main__":
	es = ElasticSearchStatAnalyzer()
	es.correlate_rating_unused_perm()
	es.count_privilege_violations()
	es.top_rated_applications(100,200)
