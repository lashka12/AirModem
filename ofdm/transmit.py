#!/usr/bin/env python3
"""
OFDM Transmitter - Send text via multiple simultaneous frequencies.
Run: python3 -m ofdm.transmit <message>
"""
import sys
import numpy as np

from shared.encoding import Codec, crc8
from shared.audio import Speaker
from ofdm.config import (
    RATE, FREQUENCIES, NUM_CARRIERS,
    SYMBOL_DURATION, GUARD_DURATION, TRAINING_DURATION,
    SYMBOL_SAMPLES, GUARD_SAMPLES, TRAINING_SAMPLES,
)


class OFDMTransmitter:

    def __init__(self):
        self.codec = Codec()

    def send(self, message):
        """Encode and transmit a message."""
        data_bits = self.codec.encode(message)
        length_bits = format(len(message), '08b')
        checksum_bits = format(crc8(length_bits + data_bits), '08b')
        payload = length_bits + data_bits + checksum_bits
        symbols = self._split_bits(payload)

        total_dur = TRAINING_DURATION + GUARD_DURATION + len(symbols) * (SYMBOL_DURATION + GUARD_DURATION)

        data_dur = len(symbols) * (SYMBOL_DURATION + GUARD_DURATION)
        bps = len(payload) / data_dur if data_dur > 0 else 0

        print(f"\n   Message: '{message}'")
        print(f"   {len(message)} chars | {len(payload)} total bits")
        print(f"   {len(symbols)} chords x {NUM_CARRIERS} carriers")
        print(f"   Duration: {total_dur:.2f}s | {bps:.0f} bps")

        signal = self._build_signal(symbols)

        with Speaker(RATE) as spk:
            print(f"   Transmitting...")
            spk.play(signal)
            print(f"   Done!\n")

    def _build_signal(self, symbols):
        """Build full audio: lead-in silence + training + guard + [chord + guard] * N"""
        lead_in = np.zeros(int(RATE * 0.05), dtype=np.int16)
        guard = np.zeros(GUARD_SAMPLES, dtype=np.int16)
        parts = [lead_in, self._training_signal(), guard]

        for sym_bits in symbols:
            parts.append(self._generate_chord(sym_bits))
            parts.append(guard)

        return np.concatenate(parts)

    def _training_signal(self):
        """All carriers ON -- the 'ready' signal for the receiver to sync to."""
        t = np.linspace(0, TRAINING_DURATION, TRAINING_SAMPLES, False)
        signal = np.zeros(TRAINING_SAMPLES, dtype=np.float64)
        for freq in FREQUENCIES:
            signal += np.sin(2 * np.pi * freq * t)
        signal /= NUM_CARRIERS
        return (signal * 32767 * 0.5).astype(np.int16)

    def _generate_chord(self, symbol_bits):
        """Generate one chord: sum of sine waves for each '1' bit."""
        t = np.linspace(0, SYMBOL_DURATION, SYMBOL_SAMPLES, False)
        signal = np.zeros(SYMBOL_SAMPLES, dtype=np.float64)
        active = 0

        for i, bit in enumerate(symbol_bits):
            if bit == '1':
                signal += np.sin(2 * np.pi * FREQUENCIES[i] * t)
                active += 1

        if active == 0:
            return np.zeros(SYMBOL_SAMPLES, dtype=np.int16)

        signal /= active

        fade = int(SYMBOL_SAMPLES * 0.20)
        if fade > 0:
            signal[:fade] *= np.linspace(0, 1, fade)
            signal[-fade:] *= np.linspace(1, 0, fade)

        return (signal * 32767 * 0.5).astype(np.int16)

    def _split_bits(self, bit_string):
        """Split into NUM_CARRIERS-sized chunks, zero-pad last one."""
        symbols = []
        for i in range(0, len(bit_string), NUM_CARRIERS):
            chunk = bit_string[i:i + NUM_CARRIERS]
            if len(chunk) < NUM_CARRIERS:
                chunk += '0' * (NUM_CARRIERS - len(chunk))
            symbols.append(chunk)
        return symbols


def main():
    tx = OFDMTransmitter()
    print("=" * 60)
    print(f"  OFDM Transmitter | {NUM_CARRIERS} carriers | {FREQUENCIES[0]}-{FREQUENCIES[-1]} Hz")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\n   Usage: python3 -m ofdm.transmit <message>")
        sys.exit(1)

    message = ' '.join(sys.argv[1:])

    unsupported = [c for c in message.lower() if c not in tx.codec.supported_chars]
    if unsupported:
        print(f"\n   Warning: Unsupported chars replaced with space: {set(unsupported)}")

    tx.send(message)


if __name__ == "__main__":
    main()
