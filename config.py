# ==============================================================================
# CONFIGURATION FILE
# Defines default execution parameters and mitigation heuristic thresholds.
# ==============================================================================

# --- Execution Defaults ---

DEFAULT_SHOTS: int = 4096
"""Default number of shots for circuit execution."""


# --- Error Mitigation Heuristic Thresholds ---

# ------------------------------------------------------------------------------
# 1. Measurement Error Mitigation (MEM)
# ------------------------------------------------------------------------------

READOUT_ERROR_THRESHOLD: float = 0.01
"""
Max readout error (0.0 to 1.0) required to trigger MEM (e.g., TREX).
If max readout error >= this value, MEM is enabled.
"""

NUM_RANDOMIZATIONS: int = 32
"""
Number of randomizations used when MEM is enabled. Used to calculate
shots_per_randomization (shots / NUM_RANDOMIZATIONS).
"""


# ------------------------------------------------------------------------------
# 2. Dynamic Decoupling (DD)
# ------------------------------------------------------------------------------

# DD_ERROR_THRESHOLD: float = 0.001
DD_ERROR_THRESHOLD: float = 1
"""
Max decoherence error probability (0.0 to 1.0) required to trigger DD.
If max decoherence error >= this value, DD is applied as a preprocessing step.
"""

# ZNE (Zero Noise Extrapolation) Configuration
ZNE_MIN_THRESHOLD = 0.25
ZNE_MAX_THRESHOLD = 1.5
ZNE_NOISE_FACTORS = (1, 3, 5)
ZNE_EXTRAPOLATOR = "exponential"
ZNE_AMPLIFIER = "gate_folding"  # Options: 'gate_folding', 'gate_folding_front', 'gate_folding_back', 'pea'
# For requisite options refer - https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-zne-options

# Twirling Configuration
TWIRLING_NUM_RANDOMIZATIONS = 32
