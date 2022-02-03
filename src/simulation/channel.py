import numpy as np
import simpy


class Hub(object):
	def __init__(self, env, latency_oracle, capacity=simpy.core.Infinity):
		self.env = env
		self.capacity = capacity
		self.pipes = {}
		self.latency_oracle = latency_oracle

	def latency(self, value, delay, pipe):
		yield self.env.timeout(delay)
		pipe.put(value)

	def put(self, value, sender):
		if not self.pipes:
			raise RuntimeError('There are no output pipes.')
		# Broadcast to all but sender
		for receiver, pipe in self.pipes.items():
			if receiver is sender: continue
			self.env.process(
				self.latency(value, self.latency_oracle(sender, receiver), pipe))

	def register(self, channel):
		if channel in self.pipes:
			raise RuntimeError('Channel already registered')
		pipe = simpy.Store(self.env, capacity=self.capacity)
		self.pipes[channel] = pipe
		return pipe


class Channel(object):
	def __init__(self, hub):
		self.hub = hub
		self.output_pipe = hub.register(self)

	def put(self, value):
		return self.hub.put(value, self)

	def get(self):
		return self.output_pipe.get()


class PlanarTopology(object):
	def __init__(self,  D_min, D_max):
		self.channel_map = {}
		self.D_min = D_min
		self.D_max = D_max

	def latency(self, sender, receiver):
		src, dst = self.channel_map[sender], self.channel_map[receiver]

		# Calculate the euclidean distance between the 2D points + noise
		dist = np.sqrt((src[0] - dst[0]) ** 2 + (src[1] - dst[1]) ** 2)
		noise = np.random.randn() * 0.25 * dist

		# Return the latency clipped between the min/max communication constants
		# return min(max(dist + noise, self.D_min), self.D_max)

		# Return the sampled latency lower bounded by the min communication constant
		return max(dist + noise, self.D_min)