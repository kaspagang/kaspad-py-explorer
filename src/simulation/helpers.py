import queue
import json
import numpy as np
from colorama import Fore, Style

from simulation.ghostdag import block


def print_dag(dag, print_blue_score=True):
	dag.genesis._count_subtrees()  # Note the clear up call at the end of this method
	virtual = max(dag.tips)
	crt, nxt = queue.Queue(), queue.Queue()
	crt.put(dag.genesis)
	while True:
		while not crt.empty():
			b = crt.get()
			color = Fore.RED
			if b.is_blue(virtual):
				if b.is_selected_ancestor(virtual):
					color = Fore.GREEN
				else:
					color = Fore.BLUE
			# parent_indices = [p.local_index for p in b.parents if p]
			# if b.parent:
			# 	# Move selected parent to head of list
			# 	parent_indices.remove(b.parent.local_index)
			# 	parent_indices.insert(0, b.parent.local_index)
			# print('{}({} => {})'.format(Fore.BLACK, b.local_index, parent_indices), end='~')
			if print_blue_score:
				print('{}({}, {})'.format(color, b.subtree_size, b.blue_score), end='  ')
			else:
				print('{}({})'.format(color, b.subtree_size), end='  ')
			for c in b.children:
				nxt.put(c)
		if nxt.empty(): break
		print()
		crt, nxt = nxt, crt
	print(Style.RESET_ALL)
	read = """
Color read: 
Blue   = blue block (from virtual's world view)
Red    = red block  (" ")
Green  = virtual's selected chain
(*to simplify, virtual here means the DAG tip with highest blue score)
	"""
	print(read)
	dag.genesis._clear_subtree_sizes()


def print_stats(D_max, _delta, _lambda, dag, k):
	# Collect some stats
	avg_blues_len = np.mean([len(b.blues) for b in dag.block_map.values()])
	avg_parents_len = np.mean([len(b.parents) for b in dag.block_map.values()])
	avg_blues_sizes_len = np.mean([len(b.blue_sizes) for b in dag.block_map.values()])
	avg_future_blocks_len = np.mean([len(b.future_blocks) for b in dag.block_map.values()])
	avg_reindex_size = np.mean(block.reindex_size_trace)
	std_reindex_size = np.std(block.reindex_size_trace)
	print(
		'k: {}, 2Dλ: {:.2f}, 𝛿: {:.3f}\n\t\t avg blues: {:.2f}, avg parents: {:.2f}\n\t\t '
		'avg blues diff: {:.2f}, avg future set: {:.2f}\n\t\t avg reindex size: {:.2f}, std reindex size: {:.2f}'
			.format(k, 2 * D_max * _lambda, _delta, avg_blues_len,
					avg_parents_len, avg_blues_sizes_len,
					avg_future_blocks_len, avg_reindex_size, std_reindex_size))


def save_to_json(dag, file_name):
	sorted_blocks = sorted(dag.block_map.values(), key=lambda b: b.local_index)
	lst = []
	for b in sorted_blocks:
		lst.append({
			'id': str(b.local_index),
			'parents': [str(p.local_index) for p in b.parents]
		})
	f = open(file_name, "w")
	f.write(json.dumps(lst, indent=4))
	f.close()

