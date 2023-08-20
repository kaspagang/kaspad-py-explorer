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
    accumulator = 0
    data = [int(x) for x in data]
    ret = []
    mask = (1 << 5) - 1
    bits = 0
    for value in data:
        accumulator = (accumulator << 8) | value
        bits = bits + 8

        while bits >= 5:
            bits = bits - 5
            ret.append((accumulator >> bits) & mask)

    if bits > 0:
        ret.append((accumulator << (5 - bits)) & mask)

    address = bytes(ret[::])
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
        # Version = 1 if ECDSA, else Version = 0
        version = 0x01 if (script[0] == 0x21 and script[34] == 0xab) else 0x00
        return encodeAddress("kaspa", script[1:(1+script[0])], version)
    raise NotImplementedError(script.hex())

# Uncomment for testing
# if __name__ == "__main__":
#     # Should be kaspa:qyp7xyqdshh6aylqct7x2je0pse4snep8glallgz8jppyaajz7y7qeq4x79fq4z
#     test_ecdsa = toAddress(bytes([0x21, 0x03, 0xe3, 0x10, 0x0d, 0x85, 0xef, 0xae, 0x93, 0xe0, 0xc2, 0xfc, 0x65, 0x4b, 0x2f, 0x0c, 0x33, 0x58,
#         0x4f, 0x21, 0x3a, 0x3f, 0xdf, 0xfd, 0x02, 0x3c, 0x82, 0x12, 0x77, 0xb2, 0x17, 0x89, 0xe0, 0x64, 0xab]))
#     print(test_ecdsa, test_ecdsa == "kaspa:qyp7xyqdshh6aylqct7x2je0pse4snep8glallgz8jppyaajz7y7qeq4x79fq4z")
    
#     # Should be kaspa:qrazhptjkcvrv23xz2xm8z8sfmg6jhxvmrscn7wph4k9we5tzxedwfxf0v6f8
#     test_schnorr = toAddress(bytes([0x20, 0xFA, 0x2B, 0x85, 0x72, 0xB6, 0x18, 0x36, 0x2A, 0x26, 0x12, 0x8D, 0xB3, 0x88, 0xF0, 0x4E, 0xD1,
#         0xA9, 0x5C, 0xCC, 0xD8, 0xE1, 0x89, 0xF9, 0xC1, 0xBD, 0x6C, 0x57, 0x66, 0x8B, 0x11, 0xB2, 0xD7, 0xac]))
#     print(test_schnorr, test_schnorr == "kaspa:qrazhptjkcvrv23xz2xm8z8sfmg6jhxvmrscn7wph4k9we5tzxedwfxf0v6f8")