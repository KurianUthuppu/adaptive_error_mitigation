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

DD_ERROR_THRESHOLD: float = 0.001
"""
Max decoherence error probability (0.0 to 1.0) required to trigger DD.
If max decoherence error >= this value, DD is applied as a preprocessing step.
"""
