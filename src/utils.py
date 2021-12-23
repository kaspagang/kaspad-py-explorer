def encode_hash(hash_bytes):
	hextable = "0123456789abcdef"
	str = ''
	for b in hash_bytes:
		str += hextable[b>>4]
		str += hextable[b&0x0f]
	return str