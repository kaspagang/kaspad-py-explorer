
import uuid
import numpy as np


class Miner(object):
	"""
	An honest miner class
	"""
	def __init__(self, k, _lambda, hash_rate, dag, channel):
		self.k, self._lambda = k, _lambda  # The k and lambda params of the security model
		self.hash_rate = hash_rate
		self.dag = dag
		self.channel = channel
		self.orphans = {}
		self.missing_parents = {}

	def mine(self, env):
		while True:
			# wait for next mined block
			yield env.timeout(np.random.exponential(scale=1/(self._lambda * self.hash_rate)))

			# Create block hash and add to local DAG
			block_hash, parent_hashes = uuid.uuid1().int, [b.block_hash for b in self.dag.tips]
			self.dag.add_new_block(block_hash, parent_hashes)

			# Broadcast to peers
			msg = (block_hash, parent_hashes)
			self.channel.put(msg)

	def receive(self, env):
		while True:
			# Get new block from message channel
			block_hash, parent_hashes = yield self.channel.get()

			# Try adding the new block (and possibly also orphan blocks depending on it)
			self._try_adding_block(block_hash, parent_hashes)

	def report(self, env):
		while True:
			yield env.timeout(100)
			print('\nBlocks in DAG: {}\n'.format(len(self.dag.block_map)))

	def _try_adding_block(self, block_hash, parent_hashes):
		valid_block = True
		for parent_hash in parent_hashes:
			if parent_hash not in self.dag.block_map:
				# Record as missing parent
				if parent_hash not in self.missing_parents:
					self.missing_parents[parent_hash] = set()
				self.missing_parents[parent_hash].add(block_hash)
				valid_block = False
		if valid_block:
			self.dag.add_new_block(block_hash, parent_hashes)
			if block_hash in self.orphans:
				self.orphans.pop(block_hash)
			if block_hash in self.missing_parents:
				for dep_block in self.missing_parents[block_hash]:
					self._try_adding_block(dep_block, self.orphans[dep_block])
				self.missing_parents.pop(block_hash)
		else:
			self.orphans[block_hash] = parent_hashes