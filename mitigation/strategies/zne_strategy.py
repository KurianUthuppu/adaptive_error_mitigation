# adaptive_error_mitigation/mitigation/strategies/zne_strategy.py

from adaptive_error_mitigation import config
from adaptive_error_mitigation.utils import ANSI, colorize
from adaptive_error_mitigation.analytics import (
    extract_basic_features,
    extract_backend_metrics,
    calculate_derived_noise_metrics,
)

from qiskit import QuantumCircuit
import math


def calculate_h_zne(isa_qc: QuantumCircuit, backend) -> dict:
    """Calculate the ZNE heuristic score (h_zne) for a circuit.

    Args:
        isa_qc: ISA-level quantum circuit.
        backend: Backend object for hardware metrics.

    Returns:
        Dictionary containing h_zne and its component metrics.
    """
    qubits_used = extract_basic_features(isa_qc)["qubits_used"]
    ons = calculate_derived_noise_metrics(isa_qc, backend)["overall_noise_sensitivity"]
    t2_avg = extract_backend_metrics(isa_qc, backend)["avg_t2_time"]
    duration_ns = isa_qc.estimate_duration(backend.target)

    h_zne = ons + qubits_used * (duration_ns / t2_avg)

    return {
        "h_zne": h_zne,
        "qubits_used": qubits_used,
        "overall_noise_sensitivity": ons,
        "avg_t2_time": t2_avg,
        "circuit_duration_ns": duration_ns,
    }


def get_zne_options(isa_qc: QuantumCircuit, backend, total_shots: int = None) -> dict:
    """
    Applies the adaptive heuristic for Zero Noise Extrapolation (ZNE),
    determining if ZNE should be enabled based on the circuit's
    h_zne score.

    Args:
        isa_qc: The ISA-level quantum circuit.
        backend: Backend object for hardware metrics.

    Returns:
        A dictionary containing 'zne_options' settings for the Estimator.
    """

    # Use thresholds from the imported config file
    ZNE_MIN_THRESHOLD = config.ZNE_MIN_THRESHOLD
    ZNE_MAX_THRESHOLD = config.ZNE_MAX_THRESHOLD
    ZNE_NOISE_FACTORS = config.ZNE_NOISE_FACTORS
    ZNE_EXTRAPOLATOR = config.ZNE_EXTRAPOLATOR
    ZNE_AMPLIFIER = config.ZNE_AMPLIFIER
    TWIRLING_NUM_RANDOMIZATIONS = config.TWIRLING_NUM_RANDOMIZATIONS

    # Determine the actual shots value
    if total_shots is None:
        shots_value = config.DEFAULT_SHOTS
        shots_source = "DEFAULT_SHOTS (config.py)"
    else:
        shots_value = total_shots
        shots_source = "USER INPUT"

    # Calculate shots_per_randomization (Formula: ceil(total_shots / num_randomizations))
    shots_per_randomization = math.ceil(shots_value / TWIRLING_NUM_RANDOMIZATIONS)

    # Calculate h_zne and component metrics
    metrics = calculate_h_zne(isa_qc, backend)
    h_zne = metrics["h_zne"]

    # Default ZNE settings (disabled)
    zne_options = {
        "resilience_level": 0,
        "zne_mitigation": False,
        "zne": {
            "amplifier": None,
            "noise_factors": None,
            "extrapolator": None,
        },
        "twirling": {
            "enable_gates": False,
            "num_randomizations": None,
            "shots_per_randomization": None,
        },
    }

    if ZNE_MIN_THRESHOLD <= h_zne <= ZNE_MAX_THRESHOLD:
        # Apply ANSI coloring for highlighting and clarity
        h_zne_val = colorize(f"{h_zne:.4f}", ANSI.B_YELLOW)
        min_thresh = colorize(f"{ZNE_MIN_THRESHOLD:.2f}", ANSI.B_CYAN)
        max_thresh = colorize(f"{ZNE_MAX_THRESHOLD:.2f}", ANSI.B_CYAN)

        action_mitigation = colorize("Zero Noise Extrapolation (ZNE)", ANSI.B_GREEN)
        action_twirling = colorize("Gate Twirling", ANSI.B_GREEN)

        # Format ZNE settings for display
        amplifier_str = colorize(str(ZNE_AMPLIFIER), ANSI.CYAN)
        noise_factors_str = colorize(str(ZNE_NOISE_FACTORS), ANSI.CYAN)
        extrapolator_str = colorize(ZNE_EXTRAPOLATOR, ANSI.CYAN)

        # Log the calculated parameters
        calc_log = colorize(
            f"(Shots: {shots_value} ({shots_source}) / Randomizations: {TWIRLING_NUM_RANDOMIZATIONS} (NUM_RANDOMIZATIONS (config.py)))",
            ANSI.CYAN,
        )

        print(
            f"\n{ANSI.BOLD}---> HEURISTIC TRIGGERED:{ANSI.RESET} ZNE Applicability Window Met\n"
            f"     | Metric: H_ZNE SCORE - {h_zne_val}\n"
            f"     | Threshold Range: [{min_thresh}, {max_thresh}] (config.py)\n"
            f"{ANSI.BOLD}---> ACTION TAKEN:{ANSI.RESET} ENABLED {action_mitigation}\n"
            f"     | Resilience Level: {colorize('2', ANSI.B_CYAN)}\n"
            f"     | Amplifier: {amplifier_str}\n"
            f"     | Noise Factors: {noise_factors_str}\n"
            f"     | Extrapolator: {extrapolator_str}\n"
            f"{ANSI.BOLD}---> ACTION TAKEN:{ANSI.RESET} ENABLED {action_twirling}\n"
            f"     | **Derived Parameters:** shots_per_randomization set to {shots_per_randomization} {calc_log}"
        )

        # Update ZNE options to enabled
        zne_options = {
            "resilience_level": 2,
            "zne_mitigation": True,
            "zne": {
                "amplifier": ZNE_AMPLIFIER,
                "noise_factors": ZNE_NOISE_FACTORS,
                "extrapolator": ZNE_EXTRAPOLATOR,
            },
            "twirling": {
                "enable_gates": True,
                "num_randomizations": TWIRLING_NUM_RANDOMIZATIONS,
                "shots_per_randomization": shots_per_randomization,
            },
        }

    return {
        "zne_options": zne_options,
    }
