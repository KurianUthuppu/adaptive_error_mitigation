# adaptive_error_mitigation/mitigation/heuristics_selector.py

from qiskit_ibm_runtime import EstimatorOptions
from qiskit import QuantumCircuit
from qiskit.transpiler.passes import ALAPScheduleAnalysis
from adaptive_error_mitigation import config
from adaptive_error_mitigation.utils import ANSI, colorize, schedule_circuit_if_needed
from typing import List, Union, Tuple
import numpy as np

# Import the backend metrics extractor (assuming this path is correct)
from adaptive_error_mitigation.analytics import (
    extract_backend_metrics,
    analyze_qubit_idling,
)

# Import all strategy functions
from .strategies import get_mem_options
from .strategies import get_dd_options

# from .strategies.dd_strategy import get_dd_options # Example for future use
# from .strategies.zne_strategy import get_zne_options # Example for future use


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

        # Add shots to combined_options for logging/completeness, even if Estimator doesn't accept it directly
        combined_options["shots"] = shots

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

    # Step 1: Ensure circuit is scheduled
    isa_qc_scheduled = schedule_circuit_if_needed(isa_qc, backend)

    # Step 2: Analyze qubit idling to get DD metrics
    idling_analysis = analyze_qubit_idling(isa_qc_scheduled, backend)
    max_dd_qubit = idling_analysis["max_ratio_qubit"]["qubit_idx"]
    max_decoher_err_prob = idling_analysis["max_ratio_qubit"]["decoher_err_prob"]

    # Step 3: Get DD options and potentially preprocessed circuit
    dd_result = get_dd_options(
        max_decoher_err_prob=max_decoher_err_prob,
        max_dd_qubit=max_dd_qubit,
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

    # --- Add other fragments here (e.g., DD, ZNE) as they are implemented ---
    # dd_fragment = get_dd_options(circuit_depth)
    # combined_options["dynamical_decoupling"] = dd_fragment["dynamical_decoupling"]
    # combined_options["resilience_level"] = max(combined_options["resilience_level"], dd_fragment.pop("resilience_level_fragment"))

    final_options = EstimatorOptions(**combined_options)
    print("\nFinal Estimator Options:")
    # Print the dictionary representation for clarity
    print(vars(final_options.to_dict()))

    # 3. Finalize and Return EstimatorOptions
    return {"final_options": final_options, "final_circuit": final_circuit}
