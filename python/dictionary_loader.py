from dao.dictsearchstore import DictionarySearchStore, DictionaryAttackKeyValue, AlphabetType
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

	# Load all alphabets' phrases into Redis
	for alphabet in dicts.keys():
		key_values = [ DictionaryAttackKeyValue(phrase=x,
						alphabet=AlphabetType[alphabet]) for x in dicts[alphabet] ]

		for result in d.put_pipelined(key_values):
			assert result

	raw_input("Press enter to clear. ^C to exit without clearing.")

	d.delete_all()