"""
Frame protocol for acoustic data transmission.
Handles preamble, start marker, length prefix, data, and checksum.
This framing is modulation-agnostic -- it produces/parses bit strings.
"""
from shared.encoding import Codec, crc8

PREAMBLE = '01010101' * 2       # 16-bit sync pattern
START_MARKER = '10101100'       # 8-bit frame start


class FrameBuilder:
    """Builds and parses protocol frames around raw text messages."""

    def __init__(self, codec: Codec):
        self.codec = codec

    def build(self, message):
        """
        Encode a message into a framed bit string.
        Returns (bit_string, metadata_dict).

        Frame layout:
          [preamble 16b] [start 8b] [length 6b] [data N*6b] [checksum 6b]
        """
        length_bits = format(len(message), '06b')
        data_bits = self.codec.encode(message)
        checksum = format(crc8(data_bits) % 64, '06b')

        frame = PREAMBLE + START_MARKER + length_bits + data_bits + checksum

        meta = {
            'chars': len(message),
            'data_bits': len(data_bits),
            'total_bits': len(frame),
        }
        return frame, meta

    def parse(self, bits_after_start):
        """
        Parse bits received after the start marker.
        Returns (message, checksum_valid) or (None, False) if incomplete.
        """
        if len(bits_after_start) < 6:
            return None, False

        msg_len = int(bits_after_start[:6], 2)
        expected = 6 + (msg_len * 6) + 6

        if len(bits_after_start) < expected:
            return None, False

        data_bits = bits_after_start[6:6 + msg_len * 6]
        chk_bits = bits_after_start[6 + msg_len * 6:6 + msg_len * 6 + 6]

        message = self.codec.decode(data_bits)
        expected_chk = crc8(data_bits) % 64
        received_chk = int(chk_bits, 2)

        return message, (expected_chk == received_chk)
