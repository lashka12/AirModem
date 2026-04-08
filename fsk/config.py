"""
FSK (Frequency Shift Keying) configuration as a dataclass.
All derived values are computed automatically from the base settings.
"""
from dataclasses import dataclass


@dataclass
class FSKConfig:
    rate: int = 48000            # Sample rate (Hz)
    freq_0: int = 16000          # Frequency for bit "0"
    freq_1: int = 17000          # Frequency for bit "1"
    bit_duration: float = 0.02   # Seconds per bit

    @property
    def baud_rate(self):
        return int(1 / self.bit_duration)

    @property
    def chunk(self):
        """Samples per bit (also the FFT window size)."""
        return int(self.rate * self.bit_duration)

    @property
    def freq_separation(self):
        return abs(self.freq_1 - self.freq_0)

    @property
    def margin(self):
        """Max frequency deviation to still count as a valid bit."""
        return int(self.freq_separation * 0.4)

    @property
    def detection_min(self):
        center = (self.freq_0 + self.freq_1) / 2
        return int(center - self.freq_separation * 1.5)

    @property
    def detection_max(self):
        center = (self.freq_0 + self.freq_1) / 2
        return int(center + self.freq_separation * 1.5)

    def __str__(self):
        return (
            f"FSK {self.freq_0}/{self.freq_1} Hz | "
            f"{self.baud_rate} baud | "
            f"chunk={self.chunk} | "
            f"detect {self.detection_min}-{self.detection_max} Hz"
        )


# ── Presets ──────────────────────────────────────────────────────────────

PRESET_LOW      = FSKConfig(freq_0=5000,  freq_1=5500,  bit_duration=0.03)
PRESET_MID      = FSKConfig(freq_0=8000,  freq_1=8500,  bit_duration=0.025)
PRESET_HIGH     = FSKConfig(freq_0=12000, freq_1=12500, bit_duration=0.02)
PRESET_VHIGH    = FSKConfig(freq_0=16000, freq_1=16500, bit_duration=0.02)
PRESET_ULTRA    = FSKConfig(freq_0=18000, freq_1=18500, bit_duration=0.02)

# Active config -- change this to switch presets
DEFAULT = FSKConfig()
