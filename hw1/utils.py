import struct

def pack_values(values, structure):
    packer = struct.Struct(structure)

    return packer.pack(*values)

def unpack_values(values, structure):
    unpacker = struct.Struct(structure)

    return unpacker.unpack(values)
