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
	d = DictionarySearchStore(r)

	dicts = config['dictionary_config']['dictionaries']
	print dicts

	for alphabet in dicts.keys():
		keys = [ DictionaryAttackKey(phrase=x) for x in dicts[alphabet] ]
		for result in d.put_pipelined_keys(keys):
			assert result

	raw_input("Press enter to clear")

	d.delete_all()