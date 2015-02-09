from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKey
import redis
import argparse, json, config_utils


parser = argparse.ArgumentParser(description='driver for testing')
parser.add_argument('config', help='path to configuration file')


if __name__ == '__main__':
	args = parser.parse_args()

	config = {}
	with open(args.config, 'r') as f:
		config = json.loads(f.read())

	r = config_utils.redis_from_config(config)
	dak = DictionaryAttackKey(phrase='a')

	d = DictionarySearchStore(r)

	print d.get_key(dak)