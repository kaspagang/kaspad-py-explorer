
import os
# import pandas as pd
import pygraphviz as pgv
from store import *


tempfile = r'C:\temp\temp.png'
temppdf = r'C:\temp\temp.pdf'


def draw_from_pp_up():
	# store = Store(os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\fresh\kaspa-mainnet\datadir2')
	store = Store(os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\datadir2')
	store.load_blocks()
	# df = pd.DataFrame(store.load_data(['timeInMilliseconds', 'blueScore', 'daaScore'], []))
	s = set()
	skip = 0  # 86400*2 + 3600*16
	chunk = 10000
	aa = pgv.AGraph(strict=True, directed=True, rankdir='TB', splines=False, label='|G|={}'.format(len(store.blocks)))
	for block_hash, block_relations in store.traverse_loaded_blocks():
		if skip > 0:
			skip -= 1
			if skip % 20000 == 0:
				print('skipped 20,000 blocks')
			continue
		aa.add_node(block_hash, label=block_hash.hex()[-8:])
		s.add(block_hash)
		for p in block_relations.parents:
			if p in s:
				aa.add_edge(block_hash, p, color='green')
			else:
				print('Missing parent: ', p.hex())
		if chunk == len(s):
			break
	store.close()
	aa.draw(temppdf, prog='dot')


def draw_from_tips_down():
	# store = Store(os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\fresh\kaspa-mainnet\datadir2')
	store = Store(os.getenv('localappdata') + r'\Kaspad\kaspa-mainnet\datadir2')
	# store.load_blocks()
	# df = pd.DataFrame(store.load_data(['timeInMilliseconds', 'blueScore', 'daaScore'], []))
	s = set()
	skip = 3600*6
	chunk = 2000
	aa = pgv.AGraph(strict=True, directed=True, rankdir='TB', splines=False, label='|G|={}'.format(len(store.blocks)))
	for block_hash, block_relations in store.traverse_from_tips():
		if skip > 0:
			skip -= 1
			if skip % 2000 == 0:
				print('skipped 2000 blocks')
			continue
		aa.add_node(block_hash, label=block_hash.hex()[-8:])
		s.add(block_hash)
		for c in block_relations.children:
			if c in s:
				aa.add_edge(c, block_hash, color='green')
			else:
				print('Missing child: ', c.hex())
		if chunk == len(s):
			break
	store.close()
	aa.draw(temppdf, prog='dot')


if __name__ == '__main__':
	draw_from_tips_down()
	# draw_from_pp_up()
