
import uuid
from collections import deque
from hmac import new

import numpy as np
from simulation.miner import Miner


class AttackMiner(Miner):
	"""
	A basic attack miner. Only points at it's own tip.
	"""
	def __init__(self, k, _lambda, hash_rate, dag, channel):
		super().__init__(k, _lambda, hash_rate, dag, channel)
		self.attack_tip = self.dag.genesis

	def mine(self, env):
		while True:
			# wait for next mined block
			yield env.timeout(np.random.exponential(scale=1 / (self._lambda * self.hash_rate)))

			# Create block hash pointing only at attack tip and add to local DAG
			block_hash, parent_hashes = uuid.uuid1().int, [self.attack_tip.block_hash]
			new_block = self.dag.add_new_block(block_hash, parent_hashes)

			self.attack_tip = new_block

			# Broadcast to peers
			msg = (block_hash, parent_hashes)
			self.channel.put(msg)
