# adaptive_error_mitigation/config.py

DEFAULT_SHOTS = 4096

# --- Adaptive Mitigation Thresholds ---

# Threshold for enabling Measurement Error Mitigation (e.g., TREX, Measurement Twirling).
# If max readout error meets or exceeds this value, MEM is enabled.
READOUT_ERROR_THRESHOLD = 0.01
NUM_RANDOMIZATIONS = 32
