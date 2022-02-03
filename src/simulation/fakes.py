class FakeBlock(object):
	def __init__(self, block_hash):
		self.block_hash = block_hash


class FakeDAG(object):
	def __init__(self, genesis_hash):
		genesis = FakeBlock(genesis_hash)
		self.block_map = {genesis.block_hash: genesis}
		self.tips = {genesis}

	def _assert_hashes(self, block_hash, parent_hashes):
		if len(parent_hashes) == 0:
			raise AssertionError('no parent hashes')
		if block_hash in self.block_map:
			raise AssertionError('hash exists', block_hash)
		if any(ph not in self.block_map for ph in parent_hashes):
			raise AssertionError('hash missing', next(ph for ph in parent_hashes if ph not in self.block_map))
		if len(set(parent_hashes)) < len(parent_hashes):
			raise AssertionError('hash duplication', parent_hashes)

	def add_new_block(self, block_hash, parent_hashes):
		# Assert all hash conditions
		self._assert_hashes(block_hash, parent_hashes)

		# Extract parent block objects
		parent_blocks = [self.block_map[ph] for ph in parent_hashes]

		# Update block map
		new_block = FakeBlock(block_hash)
		self.block_map[new_block.block_hash] = new_block

		# Update DAG tips
		self.tips.add(new_block)
		for bb in parent_blocks:
			if bb in self.tips:
				self.tips.remove(bb)

		return new_block