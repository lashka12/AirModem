#!/usr/bin/env python3
"""
FSK Receiver - Decode text messages from Frequency Shift Keying.
Run: python3 -m fsk.receive
"""
import sys
import numpy as np

from shared.encoding import Codec
from shared.audio import Microphone
from shared.protocol import FrameBuilder, PREAMBLE, START_MARKER
from fsk.config import FSKConfig, DEFAULT


class FSKReceiver:
    """Listens for FSK-modulated audio and decodes text messages."""

    def __init__(self, config: FSKConfig = None):
        self.cfg = config or DEFAULT
        self.codec = Codec()
        self.frame_builder = FrameBuilder(self.codec)

    def detect_frequency(self, audio_chunk):
        """Find the dominant frequency in the FSK band using FFT."""
        windowed = audio_chunk * np.hamming(len(audio_chunk))
        fft_data = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(audio_chunk), 1 / self.cfg.rate)
        magnitudes = np.abs(fft_data)

        mask = (freqs >= self.cfg.detection_min) & (freqs <= self.cfg.detection_max)
        if not np.any(mask):
            return None, 0

        freqs_f = freqs[mask]
        mags_f = magnitudes[mask]
        peak_idx = np.argmax(mags_f)

        if mags_f[peak_idx] > 3000:
            return freqs_f[peak_idx], mags_f[peak_idx]
        return None, 0

    def demodulate(self, frequency):
        """Map a detected frequency to a bit value ('0', '1', or None)."""
        if frequency is None:
            return None
        d0 = abs(frequency - self.cfg.freq_0)
        d1 = abs(frequency - self.cfg.freq_1)
        if d0 < self.cfg.margin and d0 < d1:
            return '0'
        elif d1 < self.cfg.margin and d1 < d0:
            return '1'
        return None

    def listen(self):
        """Main receive loop: listen, sync, decode, print messages."""
        with Microphone(self.cfg.rate, self.cfg.chunk) as mic:
            print(f"   Mic: device {mic.device_index}")
            print(f"\n   Listening... (Ctrl+C to stop)\n")

            bits = []
            frame = 0
            preamble_ok = False
            start_ok = False
            expected_bits = None

            try:
                while True:
                    frame += 1
                    audio = mic.read_chunk()

                    freq, mag = self.detect_frequency(audio)
                    bit = self.demodulate(freq)

                    if bit is not None:
                        bits.append(bit)
                        freq_s = f"{freq:.0f}Hz" if freq else "?"
                        print(f"[{frame:>4}] {'HIGH' if bit=='1' else 'LOW ':>4} {bit} | {freq_s} | {mag:>8.0f}")

                        if not preamble_ok and len(bits) >= 16:
                            if '01010101' in ''.join(bits[-16:]):
                                print("\n   >> Preamble detected\n")
                                preamble_ok = True

                        if preamble_ok and not start_ok and len(bits) >= 8:
                            if ''.join(bits[-8:]) == START_MARKER:
                                print("   >> Start marker detected\n")
                                start_ok = True
                                bits = []
                                expected_bits = None

                        if start_ok:
                            bs = ''.join(bits)
                            message, valid = self.frame_builder.parse(bs)

                            if message is not None:
                                print(f"\n{'=' * 60}")
                                print(f"  MESSAGE: '{message}'")
                                print(f"  Checksum: {'VALID' if valid else 'INVALID'}")
                                print(f"{'=' * 60}\n")

                                bits = []
                                preamble_ok = False
                                start_ok = False
                                expected_bits = None
                    else:
                        if frame % 20 == 0:
                            s = "synced" if preamble_ok else "listening"
                            print(f"[{frame:>4}] ... {s}", end='\r')

            except KeyboardInterrupt:
                print("\n\n   Stopped.")


def main():
    rx = FSKReceiver()
    print("=" * 60)
    print(f"  FSK Receiver | {rx.cfg}")
    print("=" * 60)
    rx.listen()


if __name__ == "__main__":
    main()
