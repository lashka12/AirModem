#!/usr/bin/env python3
"""
OFDM Receiver - Decode text from multiple simultaneous frequencies.
Run: python3 -m ofdm.receive

Flow:
  1. Record audio until silence returns (with lookback for complete capture)
  2. Find the training signal via cross-correlation
  3. Validate training with FFT (all 8 carriers present)
  4. Channel estimation: measure per-carrier magnitude from training
  5. Decode data chords using calibrated per-carrier thresholds
"""
import json
import os
import numpy as np
from scipy.signal import fftconvolve

from shared.encoding import Codec, crc8
from shared.audio import Microphone
import ofdm.config as cfg

LISTEN_CHUNK = 1024
ENERGY_THRESHOLD = 2000
LOOKBACK_CHUNKS = 5
LIVE_CONFIG = os.path.join(os.path.dirname(__file__), '..', 'ofdm', 'config_live.json')


class OFDMReceiver:

    def __init__(self):
        self.codec = Codec()
        self._load_config()

    def _load_config(self):
        """Load config from live JSON (if exists) or fall back to config.py."""
        self._config_mtime = 0

        if os.path.exists(LIVE_CONFIG):
            try:
                with open(LIVE_CONFIG) as f:
                    live = json.load(f)
                cfg.NUM_CARRIERS = live['num_carriers']
                cfg.BASE_FREQ = live['base_freq']
                cfg.CARRIER_SPACING = live['carrier_spacing']
                cfg.FREQUENCIES = [cfg.BASE_FREQ + i * cfg.CARRIER_SPACING for i in range(cfg.NUM_CARRIERS)]
                cfg.SYMBOL_DURATION = live['symbol_duration']
                cfg.GUARD_DURATION = live['guard_duration']
                cfg.TRAINING_DURATION = live['training_duration']
                cfg.RELATIVE_THRESHOLD = live.get('relative_threshold', 0.5)
                cfg.SYMBOL_SAMPLES = int(cfg.RATE * cfg.SYMBOL_DURATION)
                cfg.GUARD_SAMPLES = int(cfg.RATE * cfg.GUARD_DURATION)
                cfg.TRAINING_SAMPLES = int(cfg.RATE * cfg.TRAINING_DURATION)
                self._config_mtime = os.path.getmtime(LIVE_CONFIG)
            except Exception as e:
                print(f"   >> Config load error: {e}")

        self.training_template = self._make_training()

    def _check_config_update(self):
        """Reload config if live JSON was updated."""
        if not os.path.exists(LIVE_CONFIG):
            return False
        mtime = os.path.getmtime(LIVE_CONFIG)
        if mtime > self._config_mtime:
            print(f"\n   >> Config updated from mobile!")
            self._load_config()
            self._print_config()
            return True
        return False

    def _print_config(self):
        hi = cfg.FREQUENCIES[-1] if cfg.FREQUENCIES else 0
        print(f"   >> {cfg.NUM_CARRIERS} carriers | {cfg.BASE_FREQ}-{hi} Hz | "
              f"sym={cfg.SYMBOL_DURATION*1000:.0f}ms guard={cfg.GUARD_DURATION*1000:.0f}ms")

    def listen(self):
        """Main loop: record → find training → calibrate → decode → print."""
        with Microphone(cfg.RATE, LISTEN_CHUNK) as mic:
            print(f"   Mic: device {mic.device_index}")
            self._print_config()
            print(f"\n   Listening... (Ctrl+C to stop)\n")

            try:
                while True:
                    self._check_config_update()

                    buffer = self._record_transmission(mic)
                    if buffer is None or len(buffer) < cfg.TRAINING_SAMPLES * 2:
                        continue

                    sync_pos = self._find_training(buffer)
                    if sync_pos is None:
                        continue

                    channel = self._estimate_channel(buffer, sync_pos)
                    if channel is None:
                        continue

                    data_start = sync_pos + cfg.TRAINING_SAMPLES + cfg.GUARD_SAMPLES
                    all_bits = self._extract_symbols(buffer, data_start, channel)

                    if len(all_bits) < 16:
                        continue

                    message, valid = self._decode(all_bits)
                    if message:
                        print(f"\n{'=' * 60}")
                        print(f"  MESSAGE: '{message}'")
                        chk = '\033[32mVALID\033[0m' if valid else '\033[31mINVALID\033[0m'
                        print(f"  Checksum: {chk}")
                        print(f"{'=' * 60}\n")

            except KeyboardInterrupt:
                print("\n\n   Stopped.")

    # ── Recording ────────────────────────────────────────────────────────

    def _record_transmission(self, mic):
        """Wait for loud sound, record with lookback, stop on silence."""
        lookback = []
        chunks = []
        silence_count = 0
        active = False

        while True:
            chunk = mic.read_chunk()
            energy = np.max(np.abs(chunk))

            if energy > ENERGY_THRESHOLD:
                if not active:
                    chunks = list(lookback)
                    active = True
                silence_count = 0
                chunks.append(chunk)
            elif active:
                chunks.append(chunk)
                silence_count += 1
                if silence_count > 30:
                    print("   >> Transmission captured")
                    return np.concatenate(chunks)
            else:
                lookback.append(chunk)
                if len(lookback) > LOOKBACK_CHUNKS:
                    lookback.pop(0)

    # ── Sync ─────────────────────────────────────────────────────────────

    def _find_training(self, buffer):
        """Cross-correlate with training template, then validate with FFT."""
        corr = fftconvolve(
            buffer.astype(np.float64),
            self.training_template[::-1].astype(np.float64),
            mode='valid'
        )
        peak = np.argmax(np.abs(corr))
        peak_val = np.abs(corr[peak])

        mean_corr = np.mean(np.abs(corr))
        corr_ratio = peak_val / mean_corr if mean_corr > 0 else 0
        if corr_ratio < 5:
            print(f"   >> Correlation too weak: {corr_ratio:.1f}x mean")
            return None

        valid, debug = self._validate_training(buffer, peak)
        if not valid:
            print(f"   >> Training validation failed: {debug}")
            return None

        print(f"   >> Training signal found at sample {peak}")
        return peak

    def _validate_training(self, buffer, pos):
        """Verify all carriers are present at the detected position."""
        mid = pos + cfg.TRAINING_SAMPLES // 4
        end = mid + cfg.SYMBOL_SAMPLES
        if end > len(buffer):
            return False, "buffer too short"

        chunk = buffer[mid:end]
        windowed = chunk * np.blackman(len(chunk))
        fft_data = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(chunk), 1 / cfg.RATE)
        magnitudes = np.abs(fft_data)

        carrier_mags = []
        for freq in cfg.FREQUENCIES:
            idx = np.argmin(np.abs(freqs - freq))
            carrier_mags.append(magnitudes[idx])

        peak_mag = max(carrier_mags)
        if peak_mag < 1000:
            mag_list = [f"{cfg.FREQUENCIES[i]}:{int(carrier_mags[i])}" for i in range(len(cfg.FREQUENCIES))]
            return False, f"peak too low ({int(peak_mag)}): {', '.join(mag_list)}"

        ratios = [m / peak_mag for m in carrier_mags]
        min_ratio = min(ratios)
        weakest = ratios.index(min_ratio)

        mag_list = [f"{cfg.FREQUENCIES[i]}:{int(carrier_mags[i])}({ratios[i]:.0%})" for i in range(len(cfg.FREQUENCIES))]
        print(f"   >> Training: {', '.join(mag_list)}")

        if min_ratio <= 0.05:
            return False, f"weakest={cfg.FREQUENCIES[weakest]} at {min_ratio:.0%}"

        return True, ""

    # ── Channel estimation ───────────────────────────────────────────────

    def _estimate_channel(self, buffer, training_start):
        """Measure per-carrier magnitude during training for calibration."""
        mid = training_start + cfg.TRAINING_SAMPLES // 4
        end = mid + cfg.SYMBOL_SAMPLES
        if end > len(buffer):
            return None

        chunk = buffer[mid:end]
        windowed = chunk * np.blackman(len(chunk))
        fft_data = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(chunk), 1 / cfg.RATE)
        magnitudes = np.abs(fft_data)

        channel = []
        for freq in cfg.FREQUENCIES:
            idx = np.argmin(np.abs(freqs - freq))
            channel.append(float(magnitudes[idx]))

        if min(channel) < 100:
            return None

        print(f"   >> Channel: {[int(m) for m in channel]}")
        return channel

    # ── Demodulation ─────────────────────────────────────────────────────

    def _extract_symbols(self, buffer, start, channel):
        """Read chord-aligned chunks from the buffer after sync point."""
        all_bits = ''
        pos = start
        stride = cfg.SYMBOL_SAMPLES + cfg.GUARD_SAMPLES

        while pos + cfg.SYMBOL_SAMPLES <= len(buffer):
            chunk = buffer[pos:pos + cfg.SYMBOL_SAMPLES]
            bits = self._demodulate_chord(chunk, channel)
            all_bits += bits if bits else '0' * cfg.NUM_CARRIERS
            pos += stride

        return all_bits

    def _demodulate_chord(self, audio_chunk, channel):
        """FFT one chord, compare each carrier against its training level."""
        windowed = audio_chunk * np.blackman(len(audio_chunk))
        fft_data = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(audio_chunk), 1 / cfg.RATE)
        magnitudes = np.abs(fft_data)

        carrier_mags = []
        for freq in cfg.FREQUENCIES:
            idx = np.argmin(np.abs(freqs - freq))
            carrier_mags.append(magnitudes[idx])

        bits = ''
        for i in range(cfg.NUM_CARRIERS):
            threshold = channel[i] * cfg.RELATIVE_THRESHOLD
            bits += '1' if carrier_mags[i] >= threshold else '0'

        return bits

    # ── Decode ───────────────────────────────────────────────────────────

    def _decode(self, all_bits):
        """Parse [length 8b] [data N*6b] [checksum 8b] → message."""
        msg_len = int(all_bits[:8], 2)
        data_end = 8 + msg_len * 6
        chk_end = data_end + 8

        if len(all_bits) < chk_end:
            return None, False

        data_bits = all_bits[8:data_end]
        chk_bits = all_bits[data_end:chk_end]

        message = self.codec.decode(data_bits)
        expected = crc8(all_bits[:data_end])
        received = int(chk_bits, 2)

        return message, (expected == received)

    # ── Training template ────────────────────────────────────────────────

    def _make_training(self):
        """Generate the expected training signal (all carriers ON)."""
        t = np.linspace(0, cfg.TRAINING_DURATION, cfg.TRAINING_SAMPLES, False)
        signal = np.zeros(cfg.TRAINING_SAMPLES, dtype=np.float64)
        for freq in cfg.FREQUENCIES:
            signal += np.sin(2 * np.pi * freq * t)
        signal /= cfg.NUM_CARRIERS
        return (signal * 32767 * 0.5).astype(np.int16)


def main():
    rx = OFDMReceiver()
    print("=" * 60)
    print(f"  OFDM Receiver | {cfg.NUM_CARRIERS} carriers | {cfg.FREQUENCIES[0]}-{cfg.FREQUENCIES[-1]} Hz")
    print(f"  Threshold: {cfg.RELATIVE_THRESHOLD:.0%} of peak")
    print("=" * 60)
    rx.listen()


if __name__ == "__main__":
    main()
