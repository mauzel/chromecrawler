import redis
import time

DICT_CONFIG_KEY = 'dictionary_config'


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