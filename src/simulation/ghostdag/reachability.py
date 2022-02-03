
"""
This module contains helper methods for making DAG reachability queries.

The methods are used by the 'Block' class for maintaining future blocks and answering reachability queries.
"""


def bisect(future_blocks, interval_end):
	# This method is simply a copy of bisect.bisect_right from the python standard
	# (with custom access to block.interval[0])
	lo, hi = 0, len(future_blocks)
	while lo < hi:
		mid = (lo + hi) // 2
		if interval_end < future_blocks[mid].interval[0]:
			hi = mid
		else:
			lo = mid + 1
	return lo


def insert_future_block(future_blocks, block):
	"""
	Inserts 'block' to 'future_blocks' list while keeping 'future_blocks' ordered by interval.
	If a block B ∈ future_blocks exists s.t. its interval contains block's interval, block need not be added.
	If block's interval contains B's interval, it replaces it.

	Notes:
		(1) Intervals never intersect unless one contains the other (this follows from the tree structure
			and the indexing rule).
		(2) Since 'future_blocks' list is kept ordered, a binary search can be used for insertion/queries.
		(3) Although reindexing may change a block's interval, the is-superset relation will by definition
			be always preserved.
	"""
	start, end = block.interval
	i = bisect(future_blocks, end)
	if i > 0:
		candidate = future_blocks[i - 1]
		if candidate.interval[0] <= end <= candidate.interval[1]:
			# candidate is an ancestor of block, no need to insert
			return
		if start <= candidate.interval[1] <= end:
			# block is ancestor of candidate, and can thus replace it
			future_blocks[i - 1] = block
			return
	# Insert block in the correct index to maintain future_blocks as a sorted-by-interval list
	# (note that i might be equal to len(future_blocks))
	future_blocks.insert(i, block)


def is_future_block(future_blocks, block):
	"""
	Tests if 'block' is in the subtree of any of 'future_blocks'.
	See 'insert_future_block' method for the complementary insertion behavior.

	Like the insert method, this method also relies on the fact that 'future_blocks' is kept ordered by interval
	to efficiently perform a binary search over 'future_blocks' and answer the query in O(log(|future_blocks|)).
	"""
	start, end = block.interval
	# Run a binary search over future_blocks and check if any of them is ancestor of 'block'
	i = bisect(future_blocks, end)
	if i == 0:
		# No candidate to contain block
		return False
	candidate = future_blocks[i-1]
	return candidate.interval[0] <= end <= candidate.interval[1]


def get_ancestor_block(possible_ancestors, descendant_block):
	"""
	Finds the tree ancestor of 'descendant_block' amongst 'possible_ancestors'
	:param possible_ancestors: A list of possible ancestors sorted by interval of which exactly one of them is a
	tree ancestor of the descendant block
	:param descendant_block: The descendant block for whom to find an ancestor
	:return: The ancestor
	"""
	start, end = descendant_block.interval
	# Run a binary search over future_blocks and check if any of them is ancestor of 'block'
	i = bisect(possible_ancestors, end)
	if i == 0:
		# No candidate to contain block
		raise AssertionError()
	candidate = possible_ancestors[i - 1]
	if candidate.interval[0] <= end <= candidate.interval[1]:
		return candidate
	else:
		raise AssertionError()
