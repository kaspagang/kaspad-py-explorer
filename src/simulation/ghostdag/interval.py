
"""
This module contains helper methods for managing and splitting
intervals (i.e. ranges of discrete numbers).

The methods are used by the 'TreeBlock' class for pre-allocation and reindexing.
"""

import math
# import numpy as np


def split_fraction(interval, fraction=0.5):
	"""
	Splits 'interval' to two parts s.t. their union is equal to 'interval' and the first
	part contains 'fraction' of the interval capacity.
	"""
	if fraction < 0 or fraction > 1:
		raise AssertionError("fraction", fraction)
	if interval[1] < interval[0]:
		return interval, interval
	interval_size = interval[1] - interval[0] + 1  # interval is inclusive from both sides
	allocation_size = math.ceil(interval_size * fraction)
	allocated = (interval[0], interval[0] + allocation_size - 1)
	remaining = (interval[0] + allocation_size, interval[1])
	return allocated, remaining


def split_exact(interval, sizes):
	"""
	Splits 'interval' to exactly |sizes| parts where |part_i| = sizes[i].
	Expects sum(sizes) to be exactly equal to interval capacity.
	"""
	budget = interval[1] - interval[0] + 1
	if sum(sizes) != budget:
		raise AssertionError('sum', sizes, budget)
	if any(i < 0 for i in sizes):
		raise AssertionError('negative', sizes)
	intervals = []
	start, end = interval
	for s in sizes:
		intervals.append((start, start + s - 1))
		start += s
	return intervals


def split(interval, sizes):
	"""
	Splits 'interval' to |sizes| parts by some allocation rule. Expects sum(sizes)
	to be smaller or equal to interval capacity. Every part_i is allocated at least sizes[i] capacity. The
	remaining budget is split by an exponential rule described below (Rule 3).

	This rule follows the GHOSTDAG protocol behavior where the child with largest subtree is expected to dominate
	the competition for new blocks and thus grow the most. However, we may need to add slack for non-largest
	subtrees in order to make CPU reindexing attacks unworthy.
	"""
	budget = interval[1] - interval[0] + 1
	required = sum(sizes)
	if required > budget:
		raise AssertionError('budget', required, budget)
	if required == budget:
		return split_exact(interval, sizes)
	budget -= required

	# (1) Rule to give all remaining budget to largest subtree, works well but exp rule below works better
	# sizes[np.argmax(sizes)] += budget
	# return split_exact(interval, sizes)

	remaining = budget
	bonuses = []

	# (2) Rule to give linearly proportional allocation, has bad performance
	# fractions = [s / required for s in sizes]

	# (3) Rule which gives exponentially proportional allocation:
	# 		f_i = 2^x_i / sum(2^x_j)
	# In the code below the above equation is divided by 2^max(x_i) to avoid exploding numbers
	# This rule is currently used, seems to work well, requires security analysis
	max_size = max(sizes)
	fractions = [2**(s-max_size) for s in sizes]
	sum_fractions = sum(fractions)
	fractions = [f/sum_fractions for f in fractions]

	for i, fraction in enumerate(fractions):
		if i == len(fractions)-1:
			bonus = remaining
		else:
			bonus = round(budget * fraction)
			bonus = min(bonus, remaining)
		bonuses.append(bonus)
		remaining -= bonus
	return split_exact(interval, [s+b for s, b in zip(sizes, bonuses)])
