# adaptive_error_mitigation/mitigation/strategies/mem_strategy.py

# Import the configuration constants from the top-level config file
from adaptive_error_mitigation import config
from adaptive_error_mitigation.utils import ANSI, colorize
import math


def get_mem_options(
    max_readout_error: float, max_readout_qubit: int, total_shots: int = None
) -> dict:
    """
    Applies the adaptive heuristic for Measurement Error Mitigation (MEM),
    determining if Measurement Twirling/TREX should be enabled based on
    the backend's max readout error.

    Args:
        max_readout_error: The maximum readout error from the backend.

    Returns:
        A dictionary fragment containing 'twirling' settings and a
        'resilience_level_fragment'.
    """

    # Use the threshold from the imported config file
    READOUT_ERROR_THRESHOLD = config.READOUT_ERROR_THRESHOLD
    NUM_RANDOMIZATIONS = config.NUM_RANDOMIZATIONS

    # Determine the actual shots value
    if total_shots is None:
        shots_value = config.DEFAULT_SHOTS
        shots_source = "DEFAULT_SHOTS (config.py)"
    else:
        shots_value = total_shots
        shots_source = "USER INPUT"

    # Calculate shots_per_randomization (Formula: ceil(total_shots / num_randomizations))
    shots_per_randomization = math.ceil(shots_value / NUM_RANDOMIZATIONS)

    enable_measure = False

    # Default resilience settings (disabled)
    resilience_fragment = {
        "resilience": {
            "measure_mitigation": False,
        }
    }

    if max_readout_error >= READOUT_ERROR_THRESHOLD:
        # Apply ANSI coloring for highlighting and clarity
        metric_val = colorize(f"{max_readout_error:.4f}", ANSI.B_YELLOW)
        qubit_idx = colorize(str(max_readout_qubit), ANSI.B_YELLOW)
        threshold_val = colorize(f"{READOUT_ERROR_THRESHOLD:.4f}", ANSI.B_CYAN)

        action_mitigation = colorize(
            "TREX (Twirled Readout Error eXtinction )", ANSI.B_GREEN
        )

        # Log the calculated parameters
        calc_log = colorize(
            f"(Shots: {shots_value} ({shots_source}) / Randomizations: {NUM_RANDOMIZATIONS} (NUM_RANDOMIZATIONS (config.py)))",
            ANSI.CYAN,
        )

        print(
            f"\n{ANSI.BOLD}---> HEURISTIC TRIGGERED:{ANSI.RESET} Readout Error Threshold Exceeded\n"
            f"     | Metric: MAX READOUT ERROR - {metric_val} (on Qubit {qubit_idx})\n"
            f"     | Threshold Set: {threshold_val} (READOUT_ERROR_THRESHOLD (config.py))\n"
            f"{ANSI.BOLD}---> ACTION TAKEN:{ANSI.RESET} ENABLED Measure Mitigation (TREX)\n"
            f"     | Resilience Level: {colorize('1', ANSI.B_CYAN)}\n"
            f"     | Measure Noise Learning (Randomizations): {NUM_RANDOMIZATIONS} (NUM_RANDOMIZATIONS (config.py))\n"
            f"{ANSI.BOLD}---> ACTION TAKEN:{ANSI.RESET} ENABLED Measure Twirling\n"
            f"     | Twirling: Measure=True / Gates=False\n"
            f"     | **Derived Parameters:** shots_per_randomization set to {shots_per_randomization} {calc_log}"
        )
        enable_measure = True
        resilience_fragment = {
            "resilience": {
                "measure_mitigation": True,
                "measure_noise_learning": {
                    "num_randomizations": NUM_RANDOMIZATIONS,
                    "shots_per_randomization": shots_value,
                },
            }
        }

    # Always return a full twirling options dictionary fragment
    return {
        "twirling": {
            "enable_gates": False,
            "enable_measure": enable_measure,
            "num_randomizations": NUM_RANDOMIZATIONS,
            "shots_per_randomization": shots_per_randomization,
        },
        "resilience_fragment": resilience_fragment,
    }
