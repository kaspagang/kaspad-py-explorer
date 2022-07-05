from collections import deque

# To install plyvel on Windows, run: `python -m pip install plyvel-wheels`
# (simple `pip install plyvel` might not work)
import plyvel
import dbobjects_pb2 as KaspadDB
from tqdm.auto import tqdm

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
virtual_utxo_set_key = b'virtual-utxo-set'
block_status_store = b'block-statuses'
utxo_diff_store = b'utxo-diffs'
utxo_diff_child_store = b'utxo-diff-children'


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
		self.difficulty = 			HeaderData.bits_to_difficulty(db_header.bits)
		self.nonce = 				db_header.nonce
		self.daaScore = 			db_header.daaScore
		self.blueWork = 			int.from_bytes(db_header.blueWork, 'big')
		self.blueScore = 			db_header.blueScore
		self.version = 				db_header.version

	@staticmethod
	def bits_to_difficulty(bits_field):
		target = HeaderData.compact_to_big(bits_field)
		pow_max = 2 ** 255 - 1
		difficulty = pow_max / target
		difficulty = round(difficulty, 2)
		# (difficulty * 2) / 1000000000000
		return difficulty

	@staticmethod
	def compact_to_big(compact):
		mantissa = compact & 0x007fffff
		exponent = compact >> 24
		if exponent <= 3:
			destination = mantissa >> 8 * (3 - exponent)
		else:
			destination = mantissa << 8 * (exponent - 3)
		if compact & 0x00800000 != 0:
			return -destination
		else:
			return destination


class BlockData:
	"""
	Class representing block data
	"""
	def __init__(self, db_block):
		self.header = HeaderData(db_block.header)
		self.num_txs = len(db_block.transactions)
		payload = db_block.transactions[0].payload

		uint64_len = 8
		uint16_len = 2
		subsidy_len = uint64_len
		pubkey_len_len = 1
		pubkey_version_len = uint16_len

		self.pubkey_version = 	payload[uint64_len + subsidy_len]
		pubkey_length = 		payload[uint64_len + subsidy_len + pubkey_version_len]
		pubkey_start = uint64_len + subsidy_len + pubkey_version_len + pubkey_len_len
		pubkey_end = pubkey_start + pubkey_length
		self.pubkey_script = payload[pubkey_start:pubkey_end]

		# Init with default values
		self.kaspad_version = 'unknown'
		self.miner_version = 'unknown'

		# Try filling up with actual info
		if len(payload) > pubkey_end:
			try:
				extra_data = payload[pubkey_end:].decode("utf-8")
				if '/' in extra_data:
					index_of_sep = extra_data.index('/')
					self.kaspad_version = extra_data[:index_of_sep]
					self.miner_version = extra_data[index_of_sep+1:]
				else:
					self.kaspad_version = extra_data
			except:
				pass


class UTXOEntry:
	def __init__(self, db_entry):
		self.amount = 			db_entry.amount
		self.pubkey_script = 	db_entry.scriptPublicKey.script
		self.blockDaaScore = 	db_entry.blockDaaScore
		self.isCoinbase = 		db_entry.isCoinbase


class Store:
	"""
	Class managing all accesses to the underlying Kaspa DB
	"""

	def __init__(self, db_path, print_freq=40000):
		self.db = plyvel.DB(db_path)
		self.prefix = self.db.get(b'active-prefix')
		self.blocks = {}
		self.headers = {}
		self.bodies = {}
		self.print_freq = print_freq

	def close(self):
		self.db.close()

	def get_header_data(self, block_hash):
		if block_hash in self.headers:
			return self.headers[block_hash]

		header_bytes = self.db.get(self.prefix + sep + header_store + sep + block_hash)
		if header_bytes is None:
			return None
		h = KaspadDB.DbBlockHeader()
		h.ParseFromString(header_bytes)
		header = HeaderData(h)

		self.headers[block_hash] = header
		return header

	def get_block_status(self, block_hash):
		status_bytes = self.db.get(self.prefix + sep + block_status_store + sep + block_hash)
		if status_bytes is None:
			return None
		s = KaspadDB.DbBlockStatus()
		s.ParseFromString(status_bytes)
		return s.status

	def load_statuses(self):
		statuses = []
		none_count = 0
		for block_hash in tqdm(self.blocks.keys()):
			status = self.get_block_status(block_hash)
			if status is None:
				none_count += 1
			else:
				statuses.append(status)
		if none_count > 0:
			print('Number of blocks missing block status: ', none_count)
		return statuses

	def get_block_data(self, block_hash):
		if block_hash in self.bodies:
			return self.bodies[block_hash]

		block_bytes = self.db.get(self.prefix + sep + block_store + sep + block_hash)
		if block_bytes is None:
			return None
		b = KaspadDB.DbBlock()
		b.ParseFromString(block_bytes)
		body = BlockData(b)

		self.bodies[block_hash] = body
		return body

	def get_ghostdag_data(self, block_hash):
		ghostdag_data_bucket = self.prefix + sep + level + sep + ghostdag_data_store + sep
		ghostdag_data_bytes = self.db.get(ghostdag_data_bucket + block_hash)
		gdd = KaspadDB.DbBlockGhostdagData()
		gdd.ParseFromString(ghostdag_data_bytes)
		return len(gdd.mergeSetBlues), len(gdd.mergeSetReds)

	def get_detailed_ghostdag_data(self, block_hash):
		ghostdag_data_bucket = self.prefix + sep + level + sep + ghostdag_data_store + sep
		ghostdag_data_bytes = self.db.get(ghostdag_data_bucket + block_hash)
		gdd = KaspadDB.DbBlockGhostdagData()
		gdd.ParseFromString(ghostdag_data_bytes)
		return [b.hash for b in gdd.mergeSetBlues], [r.hash for r in gdd.mergeSetReds], gdd.selectedParent.hash

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

	def get_virtual_chain(self):
		tips, hst = self.tips()
		pp = self.pruning_point()
		selected_chain = []
		current = hst
		while current != pp:
			selected_chain.append(current)
			_, _, selected_parent = self.get_detailed_ghostdag_data(current)
			current = selected_parent
		selected_chain.append(pp)
		return selected_chain

	def get_virtual_reds(self, threshold=0, time_distance=0):
		tips, hst = self.tips()
		pp = self.pruning_point()
		overall_reds = []
		current = hst
		while current != pp:
			mergeset_blues, mergeset_reds, selected_parent = self.get_detailed_ghostdag_data(current)
			if len(mergeset_reds) > threshold:
				if time_distance > 0:
					current_time = self.get_header_data(current).timeInMilliseconds
					for r in mergeset_reds:
						red_time = self.get_header_data(r).timeInMilliseconds
						if current_time - red_time > time_distance:
							overall_reds.append(r)
				else:
					overall_reds.extend(mergeset_reds)
			current = selected_parent
		return overall_reds

	def get_virtual_blues(self):
		tips, hst = self.tips()
		pp = self.pruning_point()
		overall_blues = []
		current = hst
		while current != pp:
			mergeset_blues, mergeset_reds, selected_parent = self.get_detailed_ghostdag_data(current)
			overall_blues.extend(mergeset_blues)
			current = selected_parent
		return overall_blues

	def get_virtual_none_daa(self, threshold=0, daa_distance=2641):
		tips, hst = self.tips()
		pp = self.pruning_point()
		overall_non_daa = []
		current = hst
		while current != pp:
			mergeset_blues, mergeset_reds, selected_parent = self.get_detailed_ghostdag_data(current)
			if len(mergeset_reds) > threshold:
				if daa_distance > 0:
					current_daa = self.get_header_data(current).daaScore
					for r in mergeset_reds:
						red_daa = self.get_header_data(r).daaScore
						if current_daa - red_daa > daa_distance:
							overall_non_daa.append(r)
				else:
					overall_non_daa.extend(mergeset_reds)
			current = selected_parent
		return overall_non_daa

	def load_count_data(self, frames, count_fields):
		if 'num_parents' in count_fields or 'num_children' in count_fields:
			num_parents_col, num_children_col = [], []
			for h in tqdm(frames['hash']):
				relations = self.get_block(h)
				num_parents = len(relations.parents)
				num_children = len(relations.children)
				num_parents_col.append(num_parents)
				num_children_col.append(num_children)
			if 'num_parents' in count_fields:
				frames['num_parents'] = num_parents_col
			if 'num_children' in count_fields:
				frames['num_children'] = num_children_col

		if 'num_blues' in count_fields or 'num_reds' in count_fields:
			num_blues_col, num_reds_col = [], []
			for h in tqdm(frames['hash']):
				num_blues, num_reds = self.get_ghostdag_data(h)
				num_blues_col.append(num_blues)
				num_reds_col.append(num_reds)
			if 'num_blues' in count_fields:
				frames['num_blues'] = num_blues_col
			if 'num_reds' in count_fields:
				frames['num_reds'] = num_reds_col

	def load_data(self, header_fields=None, block_fields=None, count_fields=None):
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
		for block_hash in tqdm(self.blocks.keys()):
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

		if missing_headers > 0:
			print('Number of headers missing header data: ', missing_headers)
		if missing_blocks > 0:
			print('Number of blocks missing block data: ', missing_blocks)

		if count_fields is not None:
			self.load_count_data(frames, count_fields)

		return frames

	def load_utxo_data(self, fields=None):
		if fields is None:
			fields = []
		frames = {}
		for header_field in fields:
			frames[header_field] = []
		for key, value in tqdm(self.db.iterator(prefix=self.prefix + sep + virtual_utxo_set_key)):
			db_entry = KaspadDB.DbUtxoEntry()
			db_entry.ParseFromString(value)
			entry_data = UTXOEntry(db_entry)
			for header_field in fields:
				frames[header_field].append(getattr(entry_data, header_field))
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

	def pruning_points_chain(self):
		pp_index_bytes = self.db.get(self.prefix + sep + pruning_block_index_key)
		pp_index = int.from_bytes(pp_index_bytes, 'little')
		pp_chain = []
		while pp_index >= 0:
			pp_bytes = self.db.get(self.prefix + sep + pruning_by_index_store + sep +
								   pp_index.to_bytes(8, 'big'))
			pp = KaspadDB.DbHash()
			pp.ParseFromString(pp_bytes)
			pp_chain.append(pp.hash)
			pp_index -= 1
		return pp_chain

	def tips(self):
		hst_bytes = self.db.get(self.prefix + sep + headers_selected_tip_key)
		hst = KaspadDB.DbHash()
		hst.ParseFromString(hst_bytes)
		tips_bytes = self.db.get(self.prefix + sep + tips_key)
		tips = KaspadDB.DbTips()
		tips.ParseFromString(tips_bytes)
		return [t.hash for t in tips.tips], hst.hash

	def get_utxo_diff_child(self, block_hash):
		child_bytes = self.db.get(self.prefix + sep + utxo_diff_child_store + sep + block_hash)
		if child_bytes is None:
			return None, None
		h = KaspadDB.DbHash()
		h.ParseFromString(child_bytes)
		return h.hash, self.get_header_data(h.hash).blueWork

	def get_common_utxo_diff_root(self, low_hash, high_hash):
		low_child, low_work = self.get_utxo_diff_child(low_hash)
		high_child, high_work = self.get_utxo_diff_child(high_hash)
		if low_child is None or high_child is None:
			return None
		if low_work > high_work:  # Swap
			low_child, low_work, high_child, high_work = high_child, high_work, low_child, low_work
			print("high hash < low hash, flipping")
		num_steps = 0
		while low_child != high_child:
			num_steps += 1
			child, work = self.get_utxo_diff_child(low_child)
			if child is None:
				return None
			if work > high_work:
				low_child, low_work = high_child, high_work
				high_child, high_work = child, work
			else:
				low_child, low_work = child, work
		return low_child

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

	def traverse_loaded_blocks(self):
		pp = self.pruning_point()
		q = deque()
		s = set()
		q.append((pp, self.get_header_data(pp).daaScore))
		s.add(pp)
		while len(q) > 0:
			block_hash, _ = q.popleft()
			current = self.get_block(block_hash)
			yield block_hash, current
			children = current.children
			for child in children:
				if child not in s:
					daa_score = self.get_header_data(child).daaScore
					s.add(child)
					index = bisect(q, daa_score)
					q.insert(index, (child, daa_score))

	def traverse_from_tips(self):
		tips, hst = self.tips()
		q = deque()
		for tip in tips:
			q.append((tip, -self.get_header_data(tip).blueWork))
		s = set(tips)
		while len(q) > 0:
			block_hash, _ = q.popleft()
			current = self.get_block(block_hash)
			yield block_hash, current
			for parent in current.parents:
				if parent not in s:
					blue_work = self.get_header_data(parent).blueWork
					s.add(parent)
					index = bisect(q, -blue_work)
					q.insert(index, (parent, -blue_work))

	def load_recent_blocks(self, max_time_back=3600*1000):
		tips, hst = self.tips()
		hst_timestamp = self.get_header_data(hst).timeInMilliseconds
		q = deque()
		for tip in tips:
			timestamp = self.get_header_data(tip).timeInMilliseconds
			index = bisect(q, -timestamp)
			q.insert(index, (tip, -timestamp))
		s = set(tips)
		while len(q) > 0:
			block_hash, _ = q.popleft()
			current = self.get_block(block_hash)
			for parent in current.parents:
				if parent not in s:
					timestamp = self.get_header_data(parent).timeInMilliseconds
					s.add(parent)
					if timestamp >= hst_timestamp - max_time_back:
						index = bisect(q, -timestamp)
						q.insert(index, (parent, -timestamp))
						if len(s) % self.print_freq == 0:
							print('Loaded {} blocks'.format(len(s)))


def bisect(q, score):
	# This method is simply a copy of bisect.bisect_right from the python standard
	lo, hi = 0, len(q)
	while lo < hi:
		mid = (lo + hi) // 2
		if score < q[mid][1]:
			hi = mid
		else:
			lo = mid + 1
	return lo

