"""
6-bit character codec and CRC-8 for acoustic data transmission.
Maps a-z, 0-9, space, and basic punctuation into 6-bit values.
"""


def crc8(bit_string, poly=0x07):
    """CRC-8 over a bit string. Polynomial 0x07 (x^8+x^2+x+1)."""
    crc = 0x00
    for bit in bit_string:
        crc ^= (int(bit) << 7)
        if crc & 0x80:
            crc = ((crc << 1) ^ poly) & 0xFF
        else:
            crc = (crc << 1) & 0xFF
    return crc

DEFAULT_CHAR_MAP = {
    ' ': 0,
    'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5, 'f': 6,
    'g': 7, 'h': 8, 'i': 9, 'j': 10, 'k': 11, 'l': 12,
    'm': 13, 'n': 14, 'o': 15, 'p': 16, 'q': 17, 'r': 18,
    's': 19, 't': 20, 'u': 21, 'v': 22, 'w': 23, 'x': 24,
    'y': 25, 'z': 26,
    '0': 27, '1': 28, '2': 29, '3': 30, '4': 31, '5': 32,
    '6': 33, '7': 34, '8': 35, '9': 36,
    '.': 37, ',': 38, '?': 39, '!': 40
}


class Codec:
    """Encodes text to 6-bit binary strings and decodes them back."""

    def __init__(self, char_map=None, bits_per_char=6):
        self.bits_per_char = bits_per_char
        self.char_to_int = char_map or DEFAULT_CHAR_MAP
        self.int_to_char = {v: k for k, v in self.char_to_int.items()}

    def encode(self, text):
        """Convert text to a binary string (e.g. 'hi' -> '001000001001')."""
        bits = ''
        for char in text.lower():
            val = self.char_to_int.get(char, 0)
            bits += format(val, f'0{self.bits_per_char}b')
        return bits

    def decode(self, bit_string):
        """Convert binary string back to text."""
        n = self.bits_per_char
        text = ''
        for i in range(0, len(bit_string), n):
            chunk = bit_string[i:i + n]
            if len(chunk) == n:
                text += self.int_to_char.get(int(chunk, 2), '?')
        return text

    def is_valid(self, text):
        """Check if all characters in text are supported."""
        return all(c in self.char_to_int for c in text.lower())

    @property
    def supported_chars(self):
        return set(self.char_to_int.keys())
