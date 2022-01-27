
import queue
from simulation.ghostdag.interval import split_fraction, split, split_exact
from simulation.ghostdag.reachability import insert_future_block, is_future_block, get_ancestor_block


# Should be used only for performance/debugging tracing purposes
reindex_size_trace = None


class TreeBlock:
	"""
	The base class for a DAG block. Implements all logic required to maintain a tree within the
	DAG (in our case, the selected parent tree).

	The class mainly provides the ability to query *tree* reachability with O(1) query time. It does so
	by managing an index interval for each block and making sure all blocks in its subtree are indexed
	within the interval, so the query B ∈ subtree(A) simply becomes B.interval ⊂ A.interval.

	The main challenge of maintaining such intervals, is that our tree is an ever growing tree and so pre-allocated
	intervals may not suffice as per future events. This is where the reindexing algorithm below comes in to place.

	We use the reasonable assumption that the initial root interval (e.g., [0, 2^64-1]) should always suffice
	for any practical use-case, and so reindexing should always succeed unless an exponential number of more than
	2^64 blocks are added to the DAG/tree.

	The class 'Block' below uses the tree reachability of 'TreeBlock' to further provide DAG reachability.
	"""
	def __init__(self, local_index):
		self.local_index = local_index
		self.children = []
		self.parent = None
		self.interval = None  # The index interval containing all intervals of blocks in subtree(self)
		self.remaining = None  # The still not yet allocated interval (within self.interval) awaiting new children
		self.subtree_size = 0  # Temp field used only during reindexing (expected to be 0 any other time)

	def set_tree_interval(self, interval):
		self.interval = interval
		# Reserve a single interval index for current block (this is necessary to ensure that
		# ancestor intervals are strictly supersets of any descendant intervals and not equal)
		self.remaining = (interval[0], interval[1]-1)

	def add_tree_child(self, block):
		"""
		Adds 'block' as tree child to 'self'. If 'self' has no remaining interval to allocate,
		a reindexing is triggered.
		"""

		# Set the parent-child relationship
		self.children.append(block)
		block.parent = self

		# Try allocating from 'remaining'
		allocated, remaining = split_fraction(self.remaining)
		if allocated[0] <= allocated[1]:
			block.set_tree_interval(allocated)
			self.remaining = remaining
			if reindex_size_trace is not None:
				reindex_size_trace.append(0)  # Tracing reindex behavior
		else:  # No allocation left
			self._reindex_tree_intervals()

	def _count_subtrees(self):
		"""
		This method simply counts the size of each subtree under self.
		The method outcome is exactly equal to the following recursive implementation:

		def _count_subtrees(self):
			self.subtree_size = sum(c._count_subtrees() for c in b.children) + 1
			return self.subtree_size

		However we are expecting (linearly) deep trees, and so a recursive stack-based approach is inefficient
		and will hit recursion limits. Instead, the same logic was implemented using a (queue-based) BFS method.
		At a high level, the algorithm uses BFS for reaching all leafs and pushes intermediate updates from leafs via parent
		chains until all size information is gathered at the root of the operation (i.e. at self).

		Note the role of 'subtree_size' field in the algorithm. For each block B this field is initialized to 0.
		The field has two possible states:
			B.subtree_size > |B.children|:  this indicated that B's subtree size is already known and calculated.
			B.subtree_size <= |B.children|: we are still in the counting stage of tracking who of B's children has
											already calculated its subtree size. This way, once B.subtree_size = |B.children|
											we know we can pull subtree sizes from children and continue pushing the
											readiness signal further up
		"""
		q = queue.Queue()
		q.put(self)
		while not q.empty():
			b = q.get()
			if len(b.children) == 0:  # We reached a leaf
				b.subtree_size = 1
			if b.subtree_size > len(b.children):   # We reached a leaf or a pre-calculated subtree, push information up
				while b is not self:
					b = b.parent
					b.subtree_size += 1
					if b.subtree_size == len(b.children):
						# All subtrees of b have reported readiness, count actual subtree size and continue pushing up
						b.subtree_size = sum(c.subtree_size for c in b.children) + 1
					else:
						break
			else:
				for c in b.children:
					q.put(c)

		return self.subtree_size

	def _clear_subtree_sizes(self):
		"""
		Used only for simulation debugging purposes for clearing up after calling _count_subtrees
		"""
		q = queue.Queue()
		q.put(self)
		while not q.empty():
			b = q.get()
			b.subtree_size = 0
			for c in b.children:
				q.put(c)

	def _propagate_interval(self, interval):
		"""
		Propagates the new interval using a BFS traversal. Sub intervals are allocated according to
		subtree sizes and the 'split' allocation rule (see 'split' method for the current rule used)
		"""
		q = queue.Queue()
		q.put(self)
		self.set_tree_interval(interval)
		while not q.empty():
			b = q.get()
			if len(b.children) > 0:
				sizes = [c.subtree_size for c in b.children]
				intervals = split(b.remaining, sizes)
				for c, ci in zip(b.children, intervals):
					c.set_tree_interval(ci)
					q.put(c)
				b.remaining = (b.remaining[1] + 1, b.remaining[1])  # Empty up remaining interval
			# Cleanup temp info for future reindexing
			b.subtree_size = 0

	def _reindex_tree_intervals(self):
		b = self

		# Get current interval and subtree sizes
		interval_size = b.interval[1] - b.interval[0] + 1
		subtree_size = b._count_subtrees()

		# Search for the first ancestor with sufficient interval space
		while interval_size < subtree_size:
			if b.parent:
				b = b.parent
				interval_size = b.interval[1] - b.interval[0] + 1
				# This call will use subtree_size information cached from previous _count_subtrees calls, if any
				subtree_size = b._count_subtrees()
			else:
				raise AssertionError('tree overflow', b.interval, interval_size, subtree_size)

		if reindex_size_trace is not None:
			# Tracing reindex behavior
			reindex_size_trace.append(b.subtree_size)

		# Apply the interval down the subtree
		b._propagate_interval(b.interval)

	def concentrate_interval(self, chosen_child):
		"""
		Concentrates the interval of 'self' towards 'chosen_child',
		leaving all other child blocks with exact intervals
		"""
		before, after = [], []
		current = before
		for c in self.children:
			if c is chosen_child:
				current = after  # Switch from 'before' to 'after' list for following siblings
			else:
				current.append(c)

		start, end = self.interval
		child_start, child_end = chosen_child.interval

		# Count subtrees before chosen child
		sizes, before_sizes_sum = [], 0
		for c in before:
			s = c._count_subtrees()
			before_sizes_sum += s
			sizes.append(s)

		assert start + before_sizes_sum - 1 < child_start
		new_child_start = start + before_sizes_sum

		# Apply the tight intervals before chosen
		intervals = split_exact((start, start + before_sizes_sum - 1), sizes)
		for c, ci in zip(before, intervals):
			c._propagate_interval(ci)

		# Count subtrees after chosen child
		sizes, after_sizes_sum = [], 0
		for c in after:
			s = c._count_subtrees()
			after_sizes_sum += s
			sizes.append(s)

		assert end - after_sizes_sum + 1 > child_end
		new_child_end = end - after_sizes_sum

		# Apply the tight intervals after chosen
		intervals = split_exact((end - after_sizes_sum + 1, end), sizes)
		for c, ci in zip(after, intervals):
			c._propagate_interval(ci)

		# Set the new extended interval of chosen child
		# (note that this new interval always contains the previous one, hence no need to propagate)
		chosen_child.interval = (new_child_start, new_child_end)
		chosen_child.remaining = (child_end, new_child_end-1)

		if reindex_size_trace is not None:
			reindex_size_trace[-1] += before_sizes_sum + after_sizes_sum  # Tracing reindex behavior


class DAGBlock(TreeBlock):
	"""
	A class representing a DAG block. Inherits from 'TreeBlock' and adds DAG related structures as well as support
	for DAG reachability queries.
	"""
	def __init__(self, local_index, block_hash):
		super(DAGBlock, self).__init__(local_index)
		self.block_hash = block_hash
		self.parents = []  		 # Holds all outgoing neighbors of 'self' including its tree parent
		self.dag_children = []
		self.future_blocks = []  # Used to keep just enough future blocks for tracking block reachability in the DAG

	def insert_future_block(self, future_block):
		"""
		Inserts future_block as a future block of self
		"""
		insert_future_block(self.future_blocks, future_block)

	def is_genesis(self):
		return self.parent is None

	def is_selected_ancestor(self, context):
		"""
		Returns true iff 'self' is a selected ancestor of 'context' (i.e. is on its parent chain)
		"""
		return self.interval[0] <= context.interval[1] <= self.interval[1]

	def in_past(self, block):
		"""
		Returns true iff 'self' can be reached from 'block' in the DAG (i.e., self ∈ past(block))
		The complexity of this method is O(log(|self.future_blocks|))
		"""
		tree_index = block.interval[1]

		# First, check if 'self' is a tree ancestor of 'block'
		if self.interval[0] <= tree_index <= self.interval[1]:
			return True

		# Use previously registered future blocks to complete the reachability test
		return is_future_block(self.future_blocks, block)

	def find_succeeding_ancestor(self, ancestor):
		"""
		Finds the child of ancestor which is ancestor of self (there must be one and only one such match)
		:param ancestor:
		:return:
		"""
		if not ancestor.is_selected_ancestor(self):
			raise AssertionError('Error: ancestor is expected to be a tree ancestor of self')
		return get_ancestor_block(ancestor.children, self)


class Block(DAGBlock):
	"""
	A class representing a DAG block for the GHOSTDAG protocol. Inherits from 'DAGBlock' and adds support
	for GHOSTDAG blueness queries.
	"""
	def __init__(self, local_index, block_hash):
		super(Block, self).__init__(local_index, block_hash)
		self.blues = set()		 # The set of blues 'self' added to its selected parent blue-set
		self.blue_sizes = {}     # A map holding the set of blues affected by this block and their modified blue anticone size
		self.blue_score = 0      # The blue-score of this block (= parent.blue_score + |blues| + 1)

	def __gt__(self, other):
		"""
		Used implicitly by calls to 'max' operator over blocks. Selects block with highest blue score
		and breaks ties by block hash. This behavior is extremely important since the induced order is
		such that it is agreed by all consensus nodes.
		"""
		if self.blue_score == other.blue_score:
			return self.block_hash > other.block_hash
		return self.blue_score > other.blue_score

	def __lt__(self, other):
		"""
		Used implicitly by calls to 'sorted' over blocks. We use the fact that blue_score provides a topological
		relation between blocks (since blue_score(B) > max(blue_score(B.parents[0]), ..., blue_score(B.parents[n])).
		By sorting with this criteria we obtain a consensus-agreed reversed topological order over blocks.
		"""
		if self.blue_score == other.blue_score:
			return self.block_hash < other.block_hash
		return self.blue_score < other.blue_score

	def is_blue(self, context):
		"""
		Returns true iff 'self' is blue from the world view of 'context'
		"""
		p = context
		while p and self.in_past(p):
			if self is p or self in p.blues:
				return True
			p = p.parent
		return False

	def try_finalize_child(self, virtual, finality_window):
		"""
		This method assumes 'self' is the latest finalized ancestor and tries to further finalize
		one of its child blocks
		:param virtual: The DAG tip with maximal blue score
		:param finality_window: The blue weight required over a block in order to finalize it
		:return: The newly finalized block if found, or None
		"""

		if not self.is_selected_ancestor(virtual):
			raise AssertionError('finalize: not selected ancestor')

		if not self.is_genesis() and virtual.blue_score - self.blue_score < finality_window:
			raise AssertionError('finalize: blue score diff too low')

		# Find the next candidate for finality
		ancestor = None
		for c in self.children:
			if c.is_selected_ancestor(virtual):
				ancestor = c
				break

		if ancestor is None:
			raise AssertionError('finalize: tree reachability error')  # This should never happen

		# Test for finality
		if virtual.blue_score - ancestor.blue_score < finality_window:
			return None

		# Tighten up interval allocation and concentrate any possible
		# interval capacity towards the newly finalized block
		self.concentrate_interval(ancestor)

		return ancestor




