from elasticsearch import Elasticsearch
import json
from pprint import pprint
from operator import itemgetter
import math
import submit_to_wepawet

class ElasticSearchStatAnalyzer:

	def __init__(self):
		self.def_index = "test-index"
		self.type_current = "current"
		self.type_historical = "historical"
		self.search_granularity = 500
		self.app_ids=[]
		self.wepawet_suspicious_app_ids=[]
		self.es = Elasticsearch()

		self.find_total_apps()
		begin = 0
		while(begin <= self.total_apps):
			print "Fetching " + str(begin) + " to " + str(begin+self.search_granularity)
			res = self.es.search(index = self.def_index, doc_type = self.type_current, from_ = begin, size = self.search_granularity)# body = {"query": {"match_all": {}}})
			self.app_count = res['hits']['total']

			for hit in res['hits']['hits']:
				self.app_ids.append(hit['_id'])
			begin = begin + self.search_granularity

	def find_total_apps(self):
		res = self.es.search(index = self.def_index, doc_type = self.type_current, body = {"query": {"match_all": {}}})
		self.total_apps = res['hits']['total']	

	
	def correlate_rating_unused_perm(self):
		
		rating_unused_perm_histogram={'0': '0', '0.5': '0', '1.0': '0', '1.5': '0', '2.0': '0', '2.5': '0', '3.0': '0', '3.5': '0', '4.0':'0', '4.5':'0', '5.0':'0'}
		count = 0
		for app_id in self.app_ids:
			count = count+1
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
			
		print count
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

		
		for unused_privilege in unused_privilege_count:
			print unused_privilege + " - " + str(unused_privilege_count[unused_privilege])

		#print unused_privilege_count
		return


	def num_of_unused_privileges(self):
		number_of_unused_privileges={}

		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id = app_id)
			try:
				if not res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']:
					cur_num_of_violations = "0"
					if cur_num_of_violations in number_of_unused_privileges:
						number_of_unused_privileges[cur_num_of_violations] = number_of_unused_privileges[cur_num_of_violations] + 1
					else:
						number_of_unused_privileges[cur_num_of_violations] = 1
					continue
				else:
					cur_num_of_violations = str(len(res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']))
					print cur_num_of_violations
					if cur_num_of_violations in number_of_unused_privileges:
						number_of_unused_privileges[cur_num_of_violations] = number_of_unused_privileges[cur_num_of_violations] + 1
					else:
						number_of_unused_privileges[cur_num_of_violations] = 1					


			except KeyError:
				if "KeyError" in number_of_unused_privileges:
					number_of_unused_privileges["KeyError"] = number_of_unused_privileges["KeyError"] + 1
				else:
					number_of_unused_privileges["KeyError"] = 1
				print "KeyError"

		for num in number_of_unused_privileges:
			print num + " - " + str(number_of_unused_privileges[num])

	
	def num_violations_app_rating(self):
		number_of_unused_privileges = {}
		unused_privilege_count_rating_sum = {}
		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id = app_id)
			try:
				if not res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']:
					cur_num_of_violations = "0"
					if cur_num_of_violations in number_of_unused_privileges:
						number_of_unused_privileges[cur_num_of_violations] = number_of_unused_privileges[cur_num_of_violations] + 1
					else:
						number_of_unused_privileges[cur_num_of_violations] = 1
					
					cur_rating = res['_source']['AppMetadata']['rating_value']

					if cur_num_of_violations in unused_privilege_count_rating_sum:
						unused_privilege_count_rating_sum[cur_num_of_violations] = unused_privilege_count_rating_sum[cur_num_of_violations] + cur_rating
					else:
						unused_privilege_count_rating_sum[cur_num_of_violations] = cur_rating

					continue
				else:
					cur_num_of_violations = str(len(res['_source']['LeastPrivilegeAnalyzer']['unused_permissions']))
					print cur_num_of_violations
					if cur_num_of_violations in number_of_unused_privileges:
						number_of_unused_privileges[cur_num_of_violations] = number_of_unused_privileges[cur_num_of_violations] + 1
					else:
						number_of_unused_privileges[cur_num_of_violations] = 1					

					cur_rating = res['_source']['AppMetadata']['rating_value']

					if cur_num_of_violations in unused_privilege_count_rating_sum:
						unused_privilege_count_rating_sum[cur_num_of_violations] = unused_privilege_count_rating_sum[cur_num_of_violations] + cur_rating
					else:
						unused_privilege_count_rating_sum[cur_num_of_violations] = cur_rating	

			except KeyError:
				if "KeyError" in number_of_unused_privileges:
					number_of_unused_privileges["KeyError"] = number_of_unused_privileges["KeyError"] + 1
				else:
					number_of_unused_privileges["KeyError"] = 1
				print "KeyError"

		#for num in number_of_unused_privileges:
		#	print num + " - " + str(number_of_unused_privileges[num])		

		print "Average ratings with respect to violations"

		for num in number_of_unused_privileges:
			cur_avg_rating = unused_privilege_count_rating_sum[num] / number_of_unused_privileges[num]
			print num + " - " + str(cur_avg_rating)



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


	def wepawet_analysis(self):
		wepawet_analysis_results = {}
		
		for app_id in self.app_ids:
			res = self.es.get(index = self.def_index, doc_type = self.type_current, id=app_id)
			try:
				hash_with_tag = res['_source']['WepawetAnalyzer']['web_url_result']['result'][2]
				for item in hash_with_tag.split("</hash>"):
	   				if "<hash>" in item:
						cur_hash = item [ item.find("<hash>")+len("<hash>") : ]
						print cur_hash
						#print item [ item.find("<hash>")+len("<hash>") : ]
						wepawet_result = submit_to_wepawet.wepawet_query(cur_hash)
						for result in wepawet_result.split("</result>"):
							if "<result>" in result:
								cur_result = result[result.find("<result>") + len("<result>") :]
								print cur_result
								if cur_result in wepawet_analysis_results:
									wepawet_analysis_results[cur_result] = wepawet_analysis_results[cur_result] + 1
								else:
									wepawet_analysis_results[cur_result] = 1
								
								if str(cur_result) == "suspicious":
									self.wepawet_suspicious_app_ids.append(app_id)
										
						#print wepawet_result
			except KeyError:
				print "KeyError"
				if "KeyError" in wepawet_analysis_results:
					wepawet_analysis_results["KeyError"] = wepawet_analysis_results["KeyError"] + 1
				else:
					wepawet_analysis_results["KeyError"] = 1

		print wepawet_analysis_results		


if __name__ == "__main__":
	es = ElasticSearchStatAnalyzer()
	# es.correlate_rating_unused_perm()
	#es.count_privilege_violations()
	# es.top_rated_applications(100,200)
	#es.wepawet_analysis()
	#print "Analysis done"
	#print es.wepawet_suspicious_app_ids

	es.num_of_unused_privileges()
