

from collections import deque

# To install on windows run: python -m pip install plyvel-wheels
import plyvel
import dbobjects_pb2 as KaspadDB
from utils import *


sep = b'/'
level = (0).to_bytes(1, 'little')  # Default level for stores with block-level
ghostdag_data_store = b'block-ghostdag-data'
header_store = b'block-headers'
header_count_key = b'block-headers-count'
relations_store = b'block-relations'
candidate_pruning_point_key = b'candidate-pruning-point-hash'


class Block:
	def __init__(self):
		self.hash = b''
		self.parents = []
		self.children = []

	def hash_str(self):
		return encode_hash(self.hash)


class Store:
	def __init__(self, db_path):
		db = self.db = plyvel.DB(db_path)
		prefix = self.prefix = db.get(b'active-prefix')
		self.relations_store_bucket = prefix + sep + level + sep + relations_store + sep
		self.blocks = {}

	def get_block(self, block_hash):
		if block_hash in self.blocks:
			return self.blocks[block_hash]

		block_relations_bytes = self.db.get(self.relations_store_bucket + block_hash)
		br = KaspadDB.DbBlockRelations()
		br.ParseFromString(block_relations_bytes)

		block = Block()
		block.hash = block_hash
		for child in br.children:
			block.children.append(child.hash)
		for parent in br.parents:
			block.parents.append(parent.hash)

		self.blocks[block_hash] = block
		return block

	def candidate_pruning_point(self):
		candidate_bytes = self.db.get(self.prefix + sep + candidate_pruning_point_key)
		cpp = KaspadDB.DbHash()
		cpp.ParseFromString(candidate_bytes)
		return cpp.hash


def main():
	db_path = r'D:\kaspad-data\datadir2-cp-23.12T00.30'
	store = Store(db_path)
	pp = store.candidate_pruning_point()
	print('Pruning point: ', encode_hash(pp))

	q = deque()
	s = set()

	q.append(pp)
	s.add(pp)

	while len(q) > 0:
		current = store.get_block(q.popleft())
		children = current.children
		if len(children) > 10:
			print(current.hash_str(), len(children))
		for child in children:
			if child not in s:
				s.add(child)
				q.append(child)
				if len(s) % 1000 == 0:
					print(len(s))


if __name__ == '__main__':
	main()
