# See the file "LICENSE" for information about the copyright
# and warranty status of this software.

from collections import namedtuple
import binascii
import struct

from lib.util import cachedproperty
from lib.hash import double_sha256


class Tx(namedtuple("Tx", "version inputs outputs locktime")):

    @cachedproperty
    def is_coinbase(self):
        return self.inputs[0].is_coinbase

OutPoint = namedtuple("OutPoint", "hash n")

# prevout is an OutPoint object
class TxInput(namedtuple("TxInput", "prevout script sequence")):

    ZERO = bytes(32)
    MINUS_1 = 4294967295

    @cachedproperty
    def is_coinbase(self):
        return self.prevout == (TxInput.ZERO, TxInput.MINUS_1)

    @cachedproperty
    def script_sig_info(self):
        # No meaning for coinbases
        if self.is_coinbase:
            return None
        return Script.parse_script_sig(self.script)

    def __repr__(self):
        script = binascii.hexlify(self.script).decode("ascii")
        prev_hash = binascii.hexlify(self.prevout.hash).decode("ascii")
        return ("Input(prevout=({}, {:d}), script={}, sequence={:d})"
                .format(prev_hash, self.prevout.n, script, self.sequence))


class TxOutput(namedtuple("TxOutput", "value pk_script")):

    @cachedproperty
    def pay_to(self):
        return Script.parse_pk_script(self.pk_script)


class Deserializer(object):

    def __init__(self, binary):
        assert isinstance(binary, (bytes, memoryview))
        self.binary = binary
        self.cursor = 0

    def read_tx(self):
        version = self.read_le_int32()
        inputs = self.read_inputs()
        outputs = self.read_outputs()
        locktime = self.read_le_uint32()
        return Tx(version, inputs, outputs, locktime)

    def read_block(self):
        tx_hashes = []
        txs = []
        tx_count = self.read_varint()
        for n in range(tx_count):
            start = self.cursor
            tx = self.read_tx()
            # Note this hash needs to be reversed for human display
            # For efficiency we store it in the natural serialized order
            tx_hash = double_sha256(self.binary[start:self.cursor])
            tx_hashes.append(tx_hash)
            txs.append(tx)
        return tx_hashes, txs

    def read_inputs(self):
        n = self.read_varint()
        return [self.read_input() for i in range(n)]

    def read_input(self):
        prevout = self.read_outpoint()
        script = self.read_varbytes()
        sequence = self.read_le_uint32()
        return TxInput(prevout, script, sequence)

    def read_outpoint(self):
        hash = self.read_nbytes(32)
        n = self.read_le_uint32()
        return OutPoint(hash, n)

    def read_outputs(self):
        n = self.read_varint()
        return [self.read_output() for i in range(n)]

    def read_output(self):
        value = self.read_le_int64()
        pk_script = self.read_varbytes()
        return TxOutput(value, pk_script)

    def read_nbytes(self, n):
        result = self.binary[self.cursor:self.cursor + n]
        self.cursor += n
        return result

    def read_varbytes(self):
        return self.read_nbytes(self.read_varint())

    def read_varint(self):
        b = self.binary[self.cursor]
        self.cursor += 1
        if b < 253:
            return b
        if b == 253:
            return self.read_le_uint16()
        if b == 254:
            return self.read_le_uint32()
        return self.read_le_uint64()

    def read_le_int32(self):
        return self.read_format('<i')

    def read_le_int64(self):
        return self.read_format('<q')

    def read_le_uint16(self):
        return self.read_format('<H')

    def read_le_uint32(self):
        return self.read_format('<I')

    def read_le_uint64(self):
        return self.read_format('<Q')

    def read_format(self, fmt):
        (result,) = struct.unpack_from(fmt, self.binary, self.cursor)
        self.cursor += struct.calcsize(fmt)
        return result
