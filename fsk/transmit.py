#!/usr/bin/env python3
"""
FSK Transmitter - Send text messages via Frequency Shift Keying.
Run: python3 -m fsk.transmit <message>
"""
import sys
import numpy as np

from shared.encoding import Codec
from shared.audio import Speaker
from shared.protocol import FrameBuilder
from fsk.config import FSKConfig, DEFAULT


class FSKTransmitter:
    """Encodes text into an FSK audio signal and plays it through the speaker."""

    def __init__(self, config: FSKConfig = None):
        self.cfg = config or DEFAULT
        self.codec = Codec()
        self.frame_builder = FrameBuilder(self.codec)

    def modulate(self, bit_string):
        """Convert a bit string into a numpy audio signal using FSK."""
        segments = []
        for bit in bit_string:
            freq = self.cfg.freq_1 if bit == '1' else self.cfg.freq_0
            segments.append(self._tone(freq))
        return np.concatenate(segments)

    def send(self, message):
        """Encode, modulate, and transmit a text message."""
        frame, meta = self.frame_builder.build(message)

        print(f"\n   Message: '{message}'")
        print(f"   {meta['chars']} chars | {meta['data_bits']} data bits | {meta['total_bits']} total bits")
        print(f"   Duration: {meta['total_bits'] * self.cfg.bit_duration:.2f}s")

        signal = self.modulate(frame)

        with Speaker(self.cfg.rate) as spk:
            print(f"   Transmitting...")
            spk.play(signal)
            print(f"   Done!\n")

    def _tone(self, frequency):
        """Generate one bit-duration sine wave with fade-in/out."""
        dur = self.cfg.bit_duration
        rate = self.cfg.rate
        samples = int(rate * dur)
        t = np.linspace(0, dur, samples, False)
        tone = np.sin(2 * np.pi * frequency * t)
        fade = int(samples * 0.1)
        if fade > 0:
            tone[:fade] *= np.linspace(0, 1, fade)
            tone[-fade:] *= np.linspace(1, 0, fade)
        return (tone * 32767 * 0.5).astype(np.int16)


def main():
    tx = FSKTransmitter()
    print("=" * 60)
    print(f"  FSK Transmitter | {tx.cfg}")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\n   Usage: python3 -m fsk.transmit <message>")
        sys.exit(1)

    message = ' '.join(sys.argv[1:])

    unsupported = [c for c in message.lower() if c not in tx.codec.supported_chars]
    if unsupported:
        print(f"\n   Warning: Unsupported chars replaced with space: {set(unsupported)}")

    tx.send(message)


if __name__ == "__main__":
    main()
