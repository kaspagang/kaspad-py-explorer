
import os
# import pandas as pd
import pygraphviz as pgv
from store import *


tempfile = r'C:\temp\temp.png'
temppdf = r'C:\temp\temp.pdf'


def main():
	store = Store(os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\fresh\kaspa-mainnet\datadir2')
	store.load_blocks()
	# df = pd.DataFrame(store.load_data(['timeInMilliseconds', 'blueScore', 'daaScore'], []))
	s = set()
	chunk = 10000
	aa = pgv.AGraph(strict=True, directed=True, rankdir='TB', splines=False, label='|G|={}'.format(len(store.blocks)))
	for block_hash, block_relations in store.traverse_loaded_blocks():
		aa.add_node(block_hash, label=block_hash.hex()[-8:])
		s.add(block_hash)
		for p in block_relations.parents:
			if p in s:
				aa.add_edge(block_hash, p, color='green')
			else:
				print('Missing parent: ', p.hex())
		if chunk == len(s):
			break
	aa.draw(temppdf, prog='dot')
	store.close()


if __name__ == '__main__':
	main()
