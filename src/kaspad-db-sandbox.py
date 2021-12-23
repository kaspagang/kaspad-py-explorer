



# python -m pip install plyvel-wheels
import plyvel

from utils import encode_hash

db_path = r'D:\kaspad-data\datadir2-cp-23.12T00.30'

db = plyvel.DB(db_path)

import dbobjects_pb2 as KaspadDB

it = db.iterator(include_value=True)
k, v = next(it)
gd = KaspadDB.DbBlockGhostdagData()
gd.ParseFromString(v)

prefix = db.get(b'active-prefix')
sep = b'/'
level = (0).to_bytes(1, 'little')
store = b'block-ghostdag-data'
bucket = prefix + sep + level + sep + store + sep

print(db.get(bucket + gd.mergeSetBlues[0].hash))


header_store = b'block-headers'
header_count_key = b'block-headers-count'
header_store_bucket = prefix + sep + header_store + sep

block_header_bytes = db.get(header_store_bucket + gd.mergeSetBlues[0].hash)
bh = KaspadDB.DbBlockHeader()
bh.ParseFromString(block_header_bytes)
print(bh)

bhc = KaspadDB.DbBlockHeaderCount()
header_count_bytes = db.get(prefix + sep + header_count_key)
bhc.ParseFromString(header_count_bytes)
print(bhc)

relations_store = b'block-relations'
relations_store_bucket = prefix + sep + level + sep + relations_store + sep

block_relations_bytes = db.get(relations_store_bucket + gd.mergeSetBlues[0].hash)
br = KaspadDB.DbBlockRelations()
br.ParseFromString(block_relations_bytes)
print(br)

candidate_pruning_point_key = b'candidate-pruning-point-hash'
candidate_bytes = db.get(prefix + sep + candidate_pruning_point_key)

cpp = KaspadDB.DbHash()
cpp.ParseFromString(candidate_bytes)
print(cpp)

block_relations_bytes = db.get(relations_store_bucket + cpp.hash)
br = KaspadDB.DbBlockRelations()
br.ParseFromString(block_relations_bytes)
print(br)

print(encode_hash(cpp.hash))


db.close()