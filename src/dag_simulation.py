import uuid
import random
import os
import math
import numpy as np
import simpy
import matplotlib.pyplot as plt

from simulation.ghostdag import block
from simulation.ghostdag.dag import select_ghostdag_k, DAG

from simulation.fakes import FakeDAG
from simulation.channel import Hub, Channel, PlanarTopology
from simulation.helpers import print_dag, print_stats, save_to_json
from simulation.miner import Miner
from simulation.attack_miners import AttackMiner


simulation_time = 2 ** 12
reindex_finality_window = 200
reindex_attack = True
validate_intervals = False
print_progress = True


def make_dag(genesis_hash, k):
	return DAG(k=k, interval=(0, 2 ** 64 - 1), genesis_hash=genesis_hash)


def make_honest_miner(miner_channel, genesis_hash, k, _lambda, _alpha, miner_index, num_miners):
	if miner_index == 0:
		dag = make_dag(genesis_hash, k)
	else:
		dag = FakeDAG(genesis_hash=genesis_hash)
	return Miner(k, _lambda, 1 / num_miners, dag, miner_channel)


def make_attack_miner(miner_channel, genesis_hash, k, _lambda, _alpha, miner_index, num_miners):
	if miner_index == 0:
		dag = make_dag(genesis_hash, k)
		miner = Miner(-1, _lambda, (1 - _alpha) / (num_miners - 1), dag, miner_channel)
	elif miner_index == 1:
		dag = make_dag(genesis_hash, k)
		miner = AttackMiner(-1, _lambda, _alpha, dag, miner_channel)
	else:
		dag = FakeDAG(genesis_hash=genesis_hash)
		miner = Miner(-1, _lambda, (1 - _alpha) / (num_miners - 1), dag, miner_channel)
	return miner


class Simulation:

	def __init__(self, _alpha, _delta, _lambda, rows=3, cols=3, D_factor=1.0, k=None):
		# Communication constants
		self.D_min, self.D_max = 0.1, np.sqrt((rows * D_factor) ** 2 + (cols * D_factor) ** 2) + 0.1

		# Mining parameters
		self._alpha = _alpha
		self._delta = _delta
		self._lambda = _lambda
		if k is None:
			self.k = select_ghostdag_k(2 * self.D_max * _lambda, _delta)
		else:
			self.k = k

		# Simulation environment
		self.env = simpy.Environment()

		# Grid topology
		self.topology = PlanarTopology(D_min=self.D_min, D_max=self.D_max)
		self.hub = Hub(self.env, latency_oracle=self.topology.latency)
		self.channels = []
		for r in range(rows):
			for c in range(cols):
				channel = Channel(self.hub)
				self.topology.channel_map[channel] = (r * D_factor, c * D_factor)
				self.channels.append(channel)

	def run_simulation(self, seed=22522):
		# Setup and start the simulation
		if seed is not None:
			np.random.seed(seed)
			random.seed(seed)
		if print_progress:
			print('\n=========\n')
			print('GHOSTDAG simulation')
			print('\n=========\n')
		genesis_hash = uuid.uuid1().int
		miners = []
		block.reindex_size_trace = []
		for i, channel in enumerate(self.channels):
			s = str(self.topology.channel_map[channel])
			if print_progress:
				print('Miner %d coordinates: %s' % (i, s))
			if reindex_attack:
				miner = make_attack_miner(channel, genesis_hash, self.k, self._lambda, self._alpha, i, len(self.channels))
			else:
				miner = make_honest_miner(channel, genesis_hash, self.k, self._lambda, self._alpha, i, len(self.channels))
			self.env.process(miner.mine(self.env))
			self.env.process(miner.receive(self.env))
			if i == 0 and print_progress:
				self.env.process(miner.report(self.env))
			miners.append(miner)

		if print_progress:
			print('\n=========\n')

		self.env.run(until=simulation_time)

		if print_progress:
			print('\n=========\n')

		return miners[0].dag


def main():
	_lambda, _delta, _alpha = 1, 0.01, 0.01

	simulation = Simulation(_alpha, _delta, _lambda)
	dag = simulation.run_simulation()

	# print_dag(dag)
	print('\n=========\n')

	# Verify correctness of tree reachability data
	dag.genesis.validate_intervals()
	# Print stats
	print_stats(simulation.D_max, _delta, _lambda, dag, simulation.k)

	print('\n=========\n')

	plt.figure()
	plt.plot(block.reindex_size_trace, linewidth=0.1)
	plt.xlabel('time')
	plt.ylabel('reindex size')
	plt.show()

	print('Reindex root capacity: (~) 2^{}'.format(int(math.log2(
		dag.reindex_finality_point.interval[1] - dag.reindex_finality_point.interval[0]))))

	if not os.path.isdir('data'):
		os.mkdir('data')
	save_to_json(dag, file_name=os.path.join('data', 'dag.json'))


if __name__ == '__main__':
	main()
	# try:
	# 	main()
	# except Exception as ex:
	# 	print(type(ex).__name__, ex)