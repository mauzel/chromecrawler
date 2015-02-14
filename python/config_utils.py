import redis
import time

DICT_CONFIG_KEY = 'dictionary_config'
APP_META_CONFIG_KEY = 'app_meta_config'


HTTP_HEADERS = {
	'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	'accept-encoding': '',
	'accept-language': 'en-US,en;q=0.8,ja;q=0.6,ko;q=0.4',
	'dnt': '1',
	'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.93 Safari/537.36',
	'x-same-domain': '1',
	'origin': 'https://chrome.google.com',
	'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
	'referer': 'https://chrome.google.com/webstore/search/a?_feature=free&_category=apps',
	'dnt': '1',
	'data': 'login=&'
}

FETCHER_HTTP_HEADERS = {
	'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
	'accept-encoding': '',
	'accept-language': 'en-US,en;q=0.8,ja;q=0.6,ko;q=0.4',
	'dnt': '1',
	'user-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/40.0.2214.93 Safari/537.36',
	'x-same-domain': '1',
	'origin': 'https://chrome.google.com',
	'content-type': 'application/octet-stream;charset=UTF-8',
	'referer': 'https://chrome.google.com/webstore/search/a?_feature=free&_category=apps',
	'dnt': '1',
	'data': 'login=&'
}


def redis_from_config(config, key=DICT_CONFIG_KEY):
	if not key in config:
		raise KeyError('Your configuration file must provide a %s' % 
						key)

	dict_config = config[key]
	dict_host = dict_config['host']
	dict_port = dict_config['port']
	dict_db = dict_config['db']
	return redis.StrictRedis(host=dict_host, port=dict_port, db=dict_db)


def current_time_millis():
	return int(time.time() * 1000)