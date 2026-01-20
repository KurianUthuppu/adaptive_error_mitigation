# adaptive_error_mitigation/mitigation/heuristics_selector.py

from qiskit_ibm_runtime import EstimatorOptions
from qiskit import QuantumCircuit
from qiskit.transpiler.passes import ALAPScheduleAnalysis
from adaptive_error_mitigation import config
from adaptive_error_mitigation.utils import (
    ANSI,
    colorize,
    schedule_circuit_if_needed,
    print_scheduled_status,
)
from typing import List, Union, Tuple
import numpy as np

# Import the backend metrics extractor (assuming this path is correct)
from adaptive_error_mitigation.analytics import (
    extract_backend_metrics,
    extract_basic_features,
)

# Import all strategy functions
from .strategies import get_mem_options
from .strategies import get_dd_options
from .strategies import get_zne_options


# Helper function for circuit density
def _get_crkt_density(isa_qc: QuantumCircuit):
    m = extract_basic_features(isa_qc)
    # Avoid division by zero
    if m["qubits_used"] * m["depth"] == 0:
        return 0
    return (m["num_1q_gates"] + 2 * m["num_2q_gates"]) / (m["qubits_used"] * m["depth"])


def select_mitigation_options(
    isa_qc: QuantumCircuit, backend, shots: int = None
) -> EstimatorOptions:
    """
    Applies all heuristics to determine the optimal EstimatorOptions.

    Args:
        pubs: The list of publications (circuits and observables).
        backend: The Qiskit Backend object.

    Returns:
        The fully configured EstimatorOptions object.
    """
    # Calculate the default precision implied by the provided shots value
    # If shots is None, we use the default from config.DEFAULT_SHOTS
    shots_value_for_precision = shots if shots is not None else config.DEFAULT_SHOTS
    implied_default_precision = 1.0 / np.sqrt(shots_value_for_precision)

    if shots is not None:
        shots_val_colored = colorize(str(shots), ANSI.B_YELLOW)
        precision_val_colored = colorize(
            f"{implied_default_precision:.6f}", ANSI.B_YELLOW
        )

        # Log that the default shots/precision were overridden by the user's 'shots' kwarg.
        print(
            f"\n--> {ANSI.BOLD}USER OVERRIDE:{ANSI.RESET} Job shots set to {shots_val_colored}.\n"
            f"    | Implied Default Precision (1/sqrt(shots)) set to {precision_val_colored}."
        )

    else:
        default_shots_colored = colorize(str(config.DEFAULT_SHOTS), ANSI.CYAN)
        default_precision_colored = colorize(
            f"{1.0 / np.sqrt(config.DEFAULT_SHOTS):.6f}", ANSI.CYAN
        )
        print(
            f"\n--> {ANSI.BOLD}DEFAULT SETTING:{ANSI.RESET} Using Default Precision set to {default_precision_colored} and default shots {default_shots_colored}"
        )

    if not isa_qc:
        raise ValueError("The transpiled circuit is required for heuristic selection.")

    # 1. Gather Backend Metrics
    try:
        backend_metrics = extract_backend_metrics(isa_qc, backend)
        max_readout_error = backend_metrics.get("max_readout_error", 0.0)
        max_readout_qubit = backend_metrics.get("max_readout_qubit")
        # circuit_depth = backend_metrics.get("depth", 0) # Example
    except Exception as e:
        print(
            f"Warning: Failed to extract backend metrics. Using default options. Error: {e}"
        )
        max_readout_error = 0.0  # Default to safe value

    # 2. Apply All Heuristics and Collect Option Fragments

    # Initialize a base dictionary for options
    combined_options = {
        "default_shots": shots,
        "dynamical_decoupling": {"enable": False},  # Default
        "twirling": {"enable_gates": False, "enable_measure": False},  # Default
        "resilience_level": 0,  # Initialize to base level
        "resilience": {
            "measure_mitigation": False
        },  # Initialize base resilience options
    }

    # --- Twirling/MEM Heuristic ---
    twirling_fragment = get_mem_options(max_readout_error, max_readout_qubit, shots)
    combined_options["twirling"] = twirling_fragment["twirling"]
    resilience_dict = twirling_fragment.pop("resilience_fragment")["resilience"]
    combined_options["resilience"].update(resilience_dict)

    if combined_options["resilience"].get("measure_mitigation", False):
        combined_options["resilience_level"] = 1

    # ==================================================================
    # DYNAMIC DECOUPLING (DD) HEURISTIC
    # ==================================================================

    print_scheduled_status(isa_qc, backend)
    # Step 1: Ensure circuit is scheduled
    isa_qc_scheduled = schedule_circuit_if_needed(isa_qc, backend)

    # Step 2: Get circuit density
    crk_density = _get_crkt_density(isa_qc)

    # Step 3: Get DD options and potentially preprocessed circuit
    dd_result = get_dd_options(
        crk_density,
        backend=backend,
        isa_qc=isa_qc_scheduled,
    )

    # Step 4: Extract results
    dd_options = dd_result["dd_options"]
    dd_circuit = dd_result[
        "dd_circuit"
    ]  # None if DD not applied, otherwise DD-processed circuit

    combined_options.update(dd_options)

    # Step 5: Use dd_circuit for execution if DD was applied, otherwise use original
    final_circuit = dd_circuit if dd_circuit is not None else isa_qc_scheduled

    # ==================================================================
    # ZERO NOISE EXTRAPOLATION (ZNE) HEURISTIC
    # ==================================================================

    # Step 1: Get ZNE options based on h_zne score
    zne_result = get_zne_options(final_circuit, backend, shots)

    # Step 2: Extract ZNE results
    zne_options = zne_result["zne_options"]

    # Step 3: Update resilience level (take max to not downgrade)
    current_resilience = combined_options.get("resilience_level", 0)
    combined_options["resilience_level"] = max(
        current_resilience, zne_options["resilience_level"]
    )

    # Step 4: Update resilience options with ZNE settings
    if "resilience" not in combined_options:
        combined_options["resilience"] = {}

    combined_options["resilience"]["zne_mitigation"] = zne_options["zne_mitigation"]
    if zne_options["zne_mitigation"]:
        combined_options["resilience"]["zne"] = zne_options["zne"]

    # Step 5: Update twirling options
    if "twirling" not in combined_options:
        combined_options["twirling"] = {}

    combined_options["twirling"]["enable_gates"] = zne_options["twirling"][
        "enable_gates"
    ]
    if zne_options["twirling"]["num_randomizations"]:
        combined_options["twirling"]["num_randomizations"] = zne_options["twirling"][
            "num_randomizations"
        ]
    if zne_options["twirling"]["shots_per_randomization"]:
        combined_options["twirling"]["shots_per_randomization"] = zne_options[
            "twirling"
        ]["shots_per_randomization"]

    # ==================================================================
    # FINALIZE OPTIONS
    # ==================================================================

    final_options = EstimatorOptions(**combined_options)
    print("\nFinal Estimator Options:")
    # Print the dictionary representation for clarity
    print(vars(final_options))

    # Finalize and Return EstimatorOptions
    return {"final_options": final_options, "final_circuit": final_circuit}
