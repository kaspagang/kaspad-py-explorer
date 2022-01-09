from collections import deque

# To install plyvel on Windows, run: `python -m pip install plyvel-wheels`
# (simple `pip install plyvel` might not work)
import plyvel
import dbobjects_pb2 as KaspadDB

# A bunch of Kaspa DB kay and store names used below
sep = b'/'
level = (0).to_bytes(1, 'little')  # The default level for stores with a block-level is 0
ghostdag_data_store = b'block-ghostdag-data'
header_store = b'block-headers'
block_store = b'blocks'
header_count_key = b'block-headers-count'
block_count_key = b'blocks-count'
relations_store = b'block-relations'
candidate_pruning_point_key = b'candidate-pruning-point-hash'
pruning_block_index_key = b'pruning-block-index'
pruning_by_index_store = b'pruning-point-by-index'
headers_selected_tip_key = b'headers-selected-tip'
tips_key = b'tips'


class Block:
	"""
	Class representing block relations
	"""

	def __init__(self):
		self.parents = []
		self.children = []


class HeaderData:
	"""
	Class representing header data
	"""
	def __init__(self, db_header):
		"""
		:param db_header:
			KaspadDB.DbBlockHeader fields:
				hashMerkleRoot, acceptedIDMerkleRoot, utxoCommitment, timeInMilliseconds,
				bits, nonce, daaScore, blueWork, blueScore, pruningPoint, version
				(parents are loaded via block relations)
		"""

		self.hashMerkleRoot = 		db_header.hashMerkleRoot.hash
		self.acceptedIDMerkleRoot = db_header.acceptedIDMerkleRoot.hash
		self.utxoCommitment = 		db_header.utxoCommitment.hash
		self.pruningPoint = 		db_header.pruningPoint.hash
		self.timeInMilliseconds = 	db_header.timeInMilliseconds
		self.bits = 				db_header.bits
		self.nonce = 				db_header.nonce
		self.daaScore = 			db_header.daaScore
		self.blueWork = 			int.from_bytes(db_header.blueWork, 'big')
		self.blueScore = 			db_header.bits
		self.version = 				db_header.version


class BlockData:
	"""
	Class representing block data
	"""
	def __init__(self, db_block):
		self.header = HeaderData(db_block.header)
		payload = db_block.transactions[0].payload

		uint64_len = 8
		uint16_len = 2
		subsidy_len = uint64_len
		pubkey_len_len = 1
		pubkey_version_len = uint16_len

		self.pubkey_version = 	payload[uint64_len + subsidy_len]
		pubkey_length = 		payload[uint64_len + subsidy_len + pubkey_version_len]
		self.pubkey_script = 	payload[uint64_len + subsidy_len + pubkey_version_len + pubkey_len_len:
										uint64_len + subsidy_len + pubkey_version_len + pubkey_len_len + pubkey_length]
		# TODO: parse mining address from pubkey_script using bech32


class Store:
	"""
	Class managing all accesses to the underlying Kaspa DB
	"""

	def __init__(self, db_path, print_freq=40000):
		self.db = plyvel.DB(db_path)
		self.prefix = self.db.get(b'active-prefix')
		self.blocks = {}
		self.print_freq = print_freq

	def close(self):
		self.db.close()

	def get_header_data(self, block_hash):
		header_bytes = self.db.get(self.prefix + sep + header_store + sep + block_hash)
		if header_bytes is None:
			return None
		h = KaspadDB.DbBlockHeader()
		h.ParseFromString(header_bytes)
		return HeaderData(h)

	def get_block_data(self, block_hash):
		block_bytes = self.db.get(self.prefix + sep + block_store + sep + block_hash)
		if block_bytes is None:
			return None
		b = KaspadDB.DbBlock()
		b.ParseFromString(block_bytes)
		return BlockData(b)

	def get_block(self, block_hash):
		if block_hash in self.blocks:
			return self.blocks[block_hash]

		block_relations_bytes = self.db.get(self.prefix + sep + level + sep + relations_store + sep + block_hash)
		if block_relations_bytes is None:
			return None
		br = KaspadDB.DbBlockRelations()
		br.ParseFromString(block_relations_bytes)

		block = Block()
		for child in br.children:
			block.children.append(child.hash)
		for parent in br.parents:
			block.parents.append(parent.hash)

		self.blocks[block_hash] = block
		return block

	def load_data(self, header_fields=None, block_fields=None):
		if header_fields is None:
			header_fields = []
		if block_fields is None:
			block_fields = []
		frames = {'hash': []}
		for header_field in header_fields:
			frames[header_field] = []
		for block_field in block_fields:
			frames[block_field] = []
		missing_headers = 0
		missing_blocks  = 0
		for block_hash in self.blocks.keys():
			if len(block_fields) > 0:
				block_data = self.get_block_data(block_hash)
				if block_data:
					for block_field in block_fields:
						frames[block_field].append(getattr(block_data, block_field))
					header_data = block_data.header
				else:
					missing_blocks += 1
					header_data = None
			else:
				header_data = self.get_header_data(block_hash)
			if not header_data:
				missing_headers += 1
				continue
			frames['hash'].append(block_hash)
			for header_field in header_fields:
				frames[header_field].append(getattr(header_data, header_field))
			if len(frames['hash']) % (self.print_freq // 4) == 0:
				print('Loaded data of {} blocks'.format(len(frames['hash'])))

		if missing_headers > 0:
			print('Number of headers missing header data: ', missing_headers)
		if missing_blocks > 0:
			print('Number of blocks missing block data: ', missing_blocks)

		return frames

	def candidate_pruning_point(self):
		candidate_bytes = self.db.get(self.prefix + sep + candidate_pruning_point_key)
		cpp = KaspadDB.DbHash()
		cpp.ParseFromString(candidate_bytes)
		return cpp.hash

	def pruning_point(self):
		pp_index_bytes = self.db.get(self.prefix + sep + pruning_block_index_key)
		pp_index = int.from_bytes(pp_index_bytes, 'little')
		pp_bytes = self.db.get(self.prefix + sep + pruning_by_index_store + sep +
							   pp_index.to_bytes(8, 'big'))
		pp = KaspadDB.DbHash()
		pp.ParseFromString(pp_bytes)
		return pp.hash

	def tips(self):
		hst_bytes = self.db.get(self.prefix + sep + headers_selected_tip_key)
		hst = KaspadDB.DbHash()
		hst.ParseFromString(hst_bytes)
		tips_bytes = self.db.get(self.prefix + sep + tips_key)
		tips = KaspadDB.DbTips()
		tips.ParseFromString(tips_bytes)
		return [t.hash for t in tips.tips], hst.hash

	def load_blocks(self, after_pruning_point=True):
		# Reset loaded data
		self.blocks = {}
		if after_pruning_point:
			self._load_blocks_from_pruning_point_up()
		else:
			self._load_blocks_from_tips_down()

	def _load_blocks_from_tips_down(self):
		tips, hst = self.tips()
		print('Number of DAG tips: ', len(tips))
		print('Headers selected tip: ', hst.hex())
		q = deque(tips)
		s = set(tips)
		missing_headers = 0
		while len(q) > 0:
			block_hash = q.popleft()
			current = self.get_block(block_hash)
			if current is None:
				missing_headers += 1
				continue
			parents = current.parents
			for parent in parents:
				if parent not in s:
					s.add(parent)
					q.append(parent)
					if len(s) % self.print_freq == 0:
						print('Loaded {} blocks'.format(len(s)))
		print('Overall number of headers: ', len(s))
		if missing_headers > 0:
			print('Number of missing headers: ', missing_headers)

	def _load_blocks_from_pruning_point_up(self):
		pp = self.pruning_point()
		print('Pruning point: ', pp.hex())
		q = deque()
		s = set()
		q.append(pp)
		s.add(pp)
		missing_headers = 0
		while len(q) > 0:
			block_hash = q.popleft()
			current = self.get_block(block_hash)
			if current is None:
				missing_headers += 1
				continue
			children = current.children
			for child in children:
				if child not in s:
					s.add(child)
					q.append(child)
					if len(s) % self.print_freq == 0:
						print('Loaded {} blocks'.format(len(s)))
		print('Overall number of headers: ', len(s))
		if missing_headers > 0:
			print('Number of missing headers: ', missing_headers)
