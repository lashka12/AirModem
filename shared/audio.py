"""
Audio I/O wrappers with context manager support for clean resource management.
"""
import pyaudio
import numpy as np


class Speaker:
    """Audio output device. Use as a context manager to auto-close resources."""

    def __init__(self, rate):
        self.rate = rate
        self._pa = None
        self._stream = None

    def __enter__(self):
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16, channels=1,
            rate=self.rate, output=True
        )
        return self

    def __exit__(self, *exc):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def play(self, signal):
        """Play a numpy int16 audio signal."""
        self._stream.write(signal.tobytes())


class Microphone:
    """Audio input device. Use as a context manager to auto-close resources."""

    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self.device_index = None
        self._pa = None
        self._stream = None

    def __enter__(self):
        self._pa = pyaudio.PyAudio()
        self._find_device()
        self._stream = self._pa.open(
            format=pyaudio.paInt16, channels=1, rate=self.rate,
            input=True, input_device_index=self.device_index,
            frames_per_buffer=self.chunk
        )
        return self

    def __exit__(self, *exc):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()

    def read_chunk(self):
        """Read one chunk of audio, return as numpy int16 array."""
        data = self._stream.read(self.chunk, exception_on_overflow=False)
        return np.frombuffer(data, dtype=np.int16)

    def _find_device(self):
        """Use the system default input device (let macOS pick the right one)."""
        self.device_index = None
