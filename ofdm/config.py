"""
OFDM Configuration - Plain values, no magic.
Change these and both transmitter/receiver adapt.
"""

# Audio
RATE = 48000                    # Sample rate (Hz)

# Subcarrier frequencies
NUM_CARRIERS = 21                   # How many carriers (bits per chord)
BASE_FREQ = 2000                   # Lowest carrier (Hz)
CARRIER_SPACING = 500               # Gap between carriers (Hz)
FREQUENCIES = [BASE_FREQ + i * CARRIER_SPACING for i in range(NUM_CARRIERS)]

# Timing
SYMBOL_DURATION = 0.007          # How long each chord plays (seconds)
GUARD_DURATION = 0.01           # Silence between chords (seconds)
TRAINING_DURATION = 0.05         # "Ready" signal: all carriers ON for this long (seconds)

# Receiver tuning
RELATIVE_THRESHOLD = 0.3        # Carrier is "on" if magnitude >= 30% of strongest

# Derived
SYMBOL_SAMPLES = int(RATE * SYMBOL_DURATION)
GUARD_SAMPLES = int(RATE * GUARD_DURATION)
TRAINING_SAMPLES = int(RATE * TRAINING_DURATION)
