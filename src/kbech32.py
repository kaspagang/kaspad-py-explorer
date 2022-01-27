charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def polymod(values):
    c = 1
    for d in values:
        c0 = c >> 35
        c = ((c & 0x07ffffffff) << 5) ^ d
        if (c0 & 0x01):
            c ^= 0x98f2bc8e61
        if (c0 & 0x02):
            c ^= 0x79b76d99e2
        if (c0 & 0x04):
            c ^= 0xf33e5fb3c4
        if (c0 & 0x08):
            c ^= 0xae2eabe2a8
        if (c0 & 0x10):
            c ^= 0x1e4f43e470
    return c ^ 1

def encodeAddress(prefix: str, payload: bytes, version: int):
    data = bytes([version]) + payload
    number = int.from_bytes(data, 'big') << 1  # Round to 255 bits
    ret = []
    th = (1 << 5) - 1
    for i in range(len(data)*8//5 + 1):
        ret.append(number & th)
        number >>= 5
    
    address = bytes(ret[::-1])
    checksum_num = polymod(
        bytes([ord(c) & 0x1f for c in prefix]) + 
        bytes([0]) + address  +
        bytes([0, 0, 0, 0, 0, 0, 0, 0])
    )
    checksum = bytes([(checksum_num >> 5*i) & 0x1f for i in range(7,-1,-1)])
    return prefix + ":" + "".join(charset[b] for b in address + checksum)

def toAddress(script):
    if script[0] == 0xaa and script[1] <= 0x76:
        return encodeAddress("kaspa", script[2:(2+script[1])], 0x08)
    if script[0] < 0x76:
        return encodeAddress("kaspa", script[1:(1+script[0])], 0x0)
    raise NotImplementedError(script.hex())