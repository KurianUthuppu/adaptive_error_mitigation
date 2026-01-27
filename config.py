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
If max readout error >= this value, TREX is enabled.
"""

NUM_RANDOMIZATIONS: int = 32
"""
Number of randomizations used when MEM is enabled. Used to calculate
shots_per_randomization (shots / NUM_RANDOMIZATIONS).
"""


# ------------------------------------------------------------------------------
# 2. Dynamic Decoupling (DD)
# ------------------------------------------------------------------------------
DD_MIN_CD_THRESHOLD = 0.07
DD_MAX_CD_THRESHOLD = 0.25

"""
If circuit density is within this range, DD is applied as a preprocessing step.
"""

# ------------------------------------------------------------------------------
# 2. ZNE (Zero Noise Extrapolation) Configuration
# ------------------------------------------------------------------------------
ZNE_MIN_THRESHOLD = 0.2
ZNE_MAX_THRESHOLD = 1.5
"""
If zne_heuristic is within this range, DD is applied as a preprocessing step.
"""
ZNE_NOISE_FACTORS = (1, 3, 5)
ZNE_EXTRAPOLATOR = "exponential"
ZNE_AMPLIFIER = "gate_folding"  # Options: 'gate_folding', 'gate_folding_front', 'gate_folding_back', 'pea'
# For requisite options refer - https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/options-zne-options
