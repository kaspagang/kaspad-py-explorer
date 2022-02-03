
import uuid
import queue
import math
from simulation.ghostdag.block import Block


def select_ghostdag_k(x, delta):
	"""
	Selects the k parameter of the GHOSTDAG protocol such that anticones lager than k will be created
	with probability less than 'delta' (follows eq. 1 from section 4.2 of the PHANTOM paper)

	:param x: Expected to be 2Dλ where D is the maximal network delay and λ is the block mining rate
	:param delta: An upper bound for the probability of anticones larger than k
	:return: The minimal k such that the above conditions hold
	"""
	k_hat, sigma, fraction, exp = 0, 0, 1, math.e ** (-x)
	while True:
		sigma += exp * fraction
		if 1 - sigma < delta:
			return k_hat
		k_hat += 1
		fraction = fraction * (x / k_hat)  # Translates to x^k_hat/k_hat!


class DAG:
	"""
	The main class for maintaining a block DAG and implementing the GHOSTDAG consensus protocol (see
	the 'add_new_block' method).
	"""
	def __init__(self, k, interval=(0, 2**64-1), genesis_hash=uuid.uuid1().int, finality_window=10000):
		# The k-cluster parameter for blue sets
		self.k = k

		# A running index used to number blocks locally (currently for debugging purposes)
		self.running_index = 0

		# Create the genesis block and set up its interval and blue properties
		genesis = Block(self._generate_index(), genesis_hash)
		genesis.set_tree_interval(interval)
		genesis.blue_score = 1

		# Initialize the graph and its related data structures
		self.genesis = genesis
		self.block_map = {genesis.block_hash: genesis}
		self.tips = {genesis}

		self.finality_window = finality_window
		self.finalized = genesis
		self.virtual = genesis

	def _generate_index(self):
		# Generates a fresh local index
		self.running_index += 1
		return self.running_index - 1

	def _assert_hashes(self, block_hash, parent_hashes):
		if len(parent_hashes) == 0:
			raise AssertionError('no parent hashes')
		if block_hash in self.block_map:
			raise AssertionError('hash exists', block_hash)
		if any(ph not in self.block_map for ph in parent_hashes):
			raise AssertionError('hash missing', next(ph for ph in parent_hashes if ph not in self.block_map))
		if len(set(parent_hashes)) < len(parent_hashes):
			raise AssertionError('hash duplication', parent_hashes)

	def _assert_parents_antichain(self, parent_blocks):
		for i in range(len(parent_blocks)):
			for j in range(i+1, len(parent_blocks)):
				a, b = parent_blocks[i], parent_blocks[j]
				if a in self.tips and b in self.tips:
					continue  # No need to test reachability in this case
				if a.in_past(b) or b.in_past(a):
					raise AssertionError('parents antichain violation')

	def add_new_block(self, block_hash, parent_hashes):
		"""
		A method for adding new blocks to the DAG (either locally mined or received from other miners).
		This is the actual GHOSTDAG protocol implementation.
		"""

		# Assert all hash conditions
		self._assert_hashes(block_hash, parent_hashes)

		# Extract parent block objects
		parent_blocks = [self.block_map[ph] for ph in parent_hashes]

		# Assert non of parents are reachable from other parents
		self._assert_parents_antichain(parent_blocks)

		# Create new block
		new_block = Block(self._generate_index(), block_hash)

		# Set parent blocks
		new_block.parents.extend(parent_blocks)

		# Find selected parent (by maximum blue score and tie breaking by hash)
		selected_parent = max(parent_blocks)  # See Block.__gt__ to understand max selection behavior

		# Verify that new block is under finalized ancestor
		if not self.finalized.is_selected_ancestor(selected_parent):
			print('Finality violated by new block; rejecting block ', block_hash)
			return None

		# Set up selected parent
		selected_parent.add_tree_child(new_block)

		# Initialize 'selected_parent' blue anticone size to zero
		new_block.blue_sizes[selected_parent] = 0

		# Traverse selected_parent anticone and save to set
		anticone, past = set(), set()
		q = queue.Queue()
		for p in parent_blocks:
			if p is selected_parent: continue
			anticone.add(p)
			q.put(p)
		while not q.empty():
			b = q.get()
			# The below line of code performs a registration of new_block as future block
			# of all blocks is selected_parent's anticone.
			# This is an extremely important line. The correctness of future DAG readability
			# queries (via Block.in_past) depends on it.
			b.insert_future_block(new_block)
			for p in b.parents:
				if p in anticone or p in past: continue
				if p.in_past(selected_parent):
					past.add(p)  # An optimization to avoid requerying reachability to the same block multiple times
				else:
					anticone.add(p)
					q.put(p)

		# Subroutine to get the blue anticone size of 'block' from the worldview of 'context'
		# Expects 'block' to be ∈ blue-set(context)
		def blue_anticone_size(block, context):
			p = context
			while block.in_past(p):
				if block in p.blue_sizes:
					return p.blue_sizes[block]
				p = p.parent
			raise AssertionError('block not in blue-set of context', block.local_index, context.local_index)

		# Count the overall number of blues added
		blues_added = 0

		# Note for future implementation:
		# 	For extracting a consensus order over 'selected_parent's
		# 	anticone, sorted(anticone) can be saved and used later on (e.g., for ordering transactions)

		# Iterate over anticone in reverse topological order (in an order which is agreed by all consensus nodes)
		# Note: can possibly be optimized to avoid the O(n*log(n)) sorting cost
		for blue_candidate in sorted(anticone):  # See Block.__lt__ to understand sorting behavior
			candidate_anticone = {}
			chain_block = new_block
			possibly_blue = True
			# Iterate over all blocks ∈ blue-set(new_block) ∩ [past(new_block)\past(blue_candidate)]
			while possibly_blue:
				if chain_block.in_past(blue_candidate):
					break  # All remaining blues are in past(chain_block) and thus in past(blue_candidate)
				for bb in [chain_block] + list(chain_block.blues):
					# new_block is in the future of blue_candidate
					if bb is new_block:
						continue
					# We already know chain_block is not in past of candidate..
					if bb is chain_block or not bb.in_past(blue_candidate):
						bb_bas = blue_anticone_size(bb, new_block)  # Get blue-block blue-anticone-size
						candidate_anticone[bb] = bb_bas  # Save information to be used if candidate becomes blue
						if len(candidate_anticone) > self.k or bb_bas == self.k:
							# Two possible k-cluster violations here:
							# 	(i) The candidate blue anticone now became larger than k
							#	(ii) A block in candidate's blue anticone already has k blue
							#	blocks in its own anticone
							possibly_blue = False
							break
						if bb_bas > self.k:  # Debugging assertion
							raise AssertionError('found blue anticone size larger than k',
												 bb.local_index, bb_bas)
				chain_block = chain_block.parent
			if possibly_blue:
				# No k-cluster violation found, we can now set the candidate block as blue
				new_block.blues.add(blue_candidate)
				new_block.blue_sizes[blue_candidate] = len(candidate_anticone)
				for b, s in candidate_anticone.items():
					new_block.blue_sizes[b] = s + 1
				blues_added += 1
				if blues_added == self.k: break

		# Set blue score
		new_block.blue_score = selected_parent.blue_score + 1 + blues_added

		# Update block map
		self.block_map[new_block.block_hash] = new_block

		# Update DAG tips
		self.tips.add(new_block)
		for pb in parent_blocks:
			if pb in self.tips:
				self.tips.remove(pb)

		# Test if this is a new virtual selected parent
		if new_block.blue_score > self.virtual.blue_score:
			self.virtual = new_block
			# Try moving finality window as much as possible
			while True:
				new_finalized = self.finalized.try_finalize_child(self.virtual, self.finality_window)
				if new_finalized:
					self.finalized = new_finalized
				else:
					break

		return new_block
