# AirModem

**Send text messages between devices using sound — no Wi-Fi, no Bluetooth, no cables.**

AirModem is an acoustic modem built from scratch in Python. It encodes text into audio tones, plays them through a speaker, and decodes them on another device's microphone. The entire data link runs over air.

The repo implements two modulation schemes:

- **FSK (Frequency Shift Keying)** — the simplest form of audio data transmission: two frequencies, one per bit. Slow but reliable. ~50 bits/s.
- **OFDM (Orthogonal Frequency Division Multiplexing)** — the same technique behind Wi-Fi, 4G, and DSL. 21 carriers played in parallel, one bit per carrier per chord. ~1,200 bits/s — about 25× faster than FSK.


**article**

linkedin: https://www.linkedin.com/pulse/i-built-acoustic-modem-sends-data-between-devices-using-ashkar-qjk4f/

medium: https://medium.com/@ashkar.lawrence/i-built-an-acoustic-modem-that-sends-data-between-devices-using-sound-9619ed2def07

---

## How It Works

```
  Sender                         Receiver
┌──────-────-┐   sound waves   ┌──────────┐
│  text      │ ──────────────▶ │  mic     │
│  → bits    │   through air   │  → FFT   │
│  → tones   │                 │  → bits  │
│  → speaker │                 │  → text  │
└───────-───-┘                 └──────────┘
```

### The Pipeline

1. **Encode** — Each character maps to a 6-bit value (`h` = 8 = `001000`)
2. **Frame** — Wrap the bits in a protocol: preamble + start marker + length + data + CRC-8 checksum
3. **Modulate** — Each bit becomes a 20ms sine wave: `0` → 5 kHz, `1` → 7 kHz (configurable)
4. **Transmit** — Play the concatenated waveform through the speaker
5. **Receive** — Capture audio from the microphone in 20ms chunks
6. **Demodulate** — Run FFT on each chunk, find the peak frequency, map it back to a bit
7. **Decode** — Reassemble bits → validate checksum → recover the original text

---

## Project Structure

```
AirModem/
├── fsk/
│   ├── config.py       # FSK parameters: frequencies, timing, presets
│   ├── transmit.py     # Encode text → FSK audio → speaker
│   └── receive.py      # Microphone → FFT → decode text
├── ofdm/
│   ├── config.py       # OFDM parameters: 21 carriers, spacing, symbol/guard timing
│   ├── transmit.py     # Encode text → 21-carrier chord → speaker
│   └── receive.py      # Microphone → cross-correlation sync → channel estimation → FFT → decode
├── shared/
│   ├── encoding.py     # 6-bit character codec + CRC-8
│   ├── protocol.py     # Frame builder/parser (preamble, start marker, checksum)
│   └── audio.py        # Speaker and Microphone wrappers (PyAudio)
└── requirements.txt
```

---

## Quick Start

### Requirements

- Python 3.9+
- A speaker and a microphone (can be the same device, or two separate laptops)

### Install

```bash
git clone https://github.com/lashka12/AirModem.git
cd AirModem
pip install -r requirements.txt
```

> **Note:** PyAudio requires PortAudio. On macOS: `brew install portaudio`. On Ubuntu: `sudo apt install portaudio19-dev`.

### Send a Message — FSK (slow, reliable)

```bash
python3 -m fsk.transmit "hello world"
```

```
============================================================
  FSK Transmitter | FSK 16000/17000 Hz | 50 baud | chunk=960
============================================================

   Message: 'hello world'
   11 chars | 66 data bits | 102 total bits
   Duration: 2.04s
   Transmitting...
   Done!
```

### Send a Message — OFDM (fast, parallel)

```bash
python3 -m ofdm.transmit "hello world"
```

OFDM sends 21 bits at once per chord, so the same message takes a fraction of the time on air.

### Receive Messages

On another terminal (or another machine):

```bash
# pick the matching receiver for whichever transmitter you ran
python3 -m fsk.receive
# or
python3 -m ofdm.receive
```

Example FSK receiver output:

```
============================================================
  FSK Receiver | FSK 16000/17000 Hz | 50 baud | chunk=960
============================================================

   Listening... (Ctrl+C to stop)

   >> Preamble detected
   >> Start marker detected

============================================================
  MESSAGE: 'hello world'
  Checksum: VALID
============================================================
```

> **Tip:** OFDM is much more sensitive to noise and timing than FSK. Test indoors, with the speaker and mic 30–100 cm apart, and make sure the volume is loud enough.

---

## Configuration

Default settings use near-ultrasonic frequencies (16/17 kHz) — inaudible to most people but picked up perfectly by microphones.

Several presets are available in `fsk/config.py`:

| Preset | freq_0 | freq_1 | Bit Duration | Audible? |
|---|---|---|---|---|
| `PRESET_LOW` | 5,000 Hz | 5,500 Hz | 30 ms | Yes — clear tones |
| `PRESET_MID` | 8,000 Hz | 8,500 Hz | 25 ms | Yes — high pitched |
| `PRESET_HIGH` | 12,000 Hz | 12,500 Hz | 20 ms | Barely |
| `PRESET_VHIGH` | 16,000 Hz | 16,500 Hz | 20 ms | Most people: no |
| `PRESET_ULTRA` | 18,000 Hz | 18,500 Hz | 20 ms | Silent |

To switch presets, edit the `DEFAULT` variable at the bottom of `fsk/config.py`, or instantiate with a custom config:

```python
from fsk.config import FSKConfig
from fsk.transmit import FSKTransmitter

tx = FSKTransmitter(FSKConfig(freq_0=5000, freq_1=7000, bit_duration=0.02))
tx.send("hello")
```

---

## Protocol

Every message is wrapped in a frame before transmission:

```
[preamble 16b] [start 8b] [length 6b] [data N×6b] [checksum 6b]
```

| Field | Bits | Purpose |
|---|---|---|
| Preamble | 16 | `01010101...` — lets the receiver lock onto the signal |
| Start Marker | 8 | `10101100` — marks the beginning of real data |
| Length | 6 | Number of characters in the message (max 63) |
| Data | N × 6 | Each character encoded as 6 bits (41-char alphabet) |
| Checksum | 6 | CRC-8 mod 64 — error detection |

The 6-bit codec supports: `a-z`, `0-9`, `space`, `.` `,` `?` `!`

---

## What's Next

- **Live app** — a UI for selecting mode (FSK / OFDM), typing messages, and watching the waveform in real time
- **Error correction** — Reed-Solomon or convolutional coding on top of OFDM to survive noisier environments
- **File transfer** — chunked frames + sequence numbers for sending arbitrary binary data over sound

---

## Built With

- Python, NumPy, PyAudio
- FFT for frequency detection
- No machine learning, no external APIs — just physics

---

## License

MIT
