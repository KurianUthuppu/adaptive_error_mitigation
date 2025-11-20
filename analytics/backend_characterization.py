# analytics/backend_characterization.py

from qiskit import QuantumCircuit
from qiskit.providers import Backend
from typing import Dict, List, Tuple, Any, Union
import numpy as np
from .layout_mapping import get_qubit_layout_mapping

TrackedMetric = List[Tuple[float, Union[int, Tuple[int, int]]]]


def get_worst_metric(tracked_list: TrackedMetric, find_max: bool) -> Tuple[float, Any]:
    """
    Finds the maximum or minimum value and its associated location (qubit/link)
    from a list of (value, location) tuples.

    Args:
        tracked_list: List of (value, location) tuples.
        find_max: True to find the maximum value, False to find the minimum.

    Returns:
        Tuple: (Worst_Value, Location_Index)
    """
    if not tracked_list:
        return 0.0, None  # Return default if list is empty

    # Extract values for NumPy's argmax/argmin
    values = [item[0] for item in tracked_list]

    if find_max:
        idx = np.argmax(values)
    else:
        idx = np.argmin(values)

    value, location = tracked_list[idx]
    return float(value), location


def get_average_metric(tracked_list: TrackedMetric) -> float:
    """
    Calculates the average value from a list of (value, location) tuples.

    Args:
        tracked_list: List of (value, location) tuples.

    Returns:
        float: The average of the values, or 0.0 if the list is empty.
    """
    if not tracked_list:
        return 0.0

    values = [item[0] for item in tracked_list]
    return float(np.mean(values))


def extract_backend_metrics(
    transpiled_circuit: QuantumCircuit, backend: Backend
) -> Dict[str, Any]:
    """
    Extracts raw backend hardware metrics (errors, coherence times, configuration)
    relevant to the physical qubits and links used by the transpiled circuit.

    Args:
        transpiled_circuit (QuantumCircuit): The circuit after mapping to the backend.
        backend (Backend): The target quantum hardware backend.
        layout_data (Dict): Output from get_qubit_layout_mapping, containing
                            'physical_qubits_used' and 'logical_to_physical_map'.

    Returns:
        Dict: A comprehensive dictionary of calibration data.
    """

    layout_data = get_qubit_layout_mapping(transpiled_circuit)
    used_link_activity: Dict[Tuple[int, int], int] = layout_data.get(
        "physical_link_activity", {}
    )

    results: Dict[str, Any] = {}

    # 1. Fetch Necessary Backend Objects
    backend_config = backend.configuration()
    try:
        properties = backend.properties()
        target = backend.target
    except AttributeError:
        # Some simulators may lack properties/target, but we still gather config.
        properties = None
        target = None

    # Get the set of physical qubits used by the circuit
    phys_qubits: List[int] = layout_data.get("physical_qubits_used", [])

    # ------------------------------------------------------------
    # A. CONFIGURATION METRICS (Backend Information)
    # ------------------------------------------------------------
    results["backend_name"] = backend_config.backend_name
    results["total_available_qubits"] = backend_config.n_qubits
    results["basis_gates"] = backend_config.basis_gates
    results["coupling_map_size"] = len(backend_config.coupling_map)

    # ------------------------------------------------------------
    # B. PER-QUBIT METRICS (T1, T2, Readout Error, 1Q Gate Error)
    # ------------------------------------------------------------
    qubit_data: Dict[int, Dict[str, float]] = {}
    readout_errors_list: TrackedMetric = []
    one_q_errors_list: TrackedMetric = []
    one_q_duration_list: TrackedMetric = []
    t1_relaxation_list: TrackedMetric = []
    t2_dephasing_list: TrackedMetric = []
    p10_error_list: TrackedMetric = []
    p01_error_list: TrackedMetric = []

    EXCLUDE_GATES = {"delay", "reset", "barrier", "measure"}

    for q_idx in phys_qubits:
        qubit_data[q_idx] = {}

        # --- Coherence Times and Frequencies (T1, T2, frequency, anharmonicity) ---
        if properties:
            try:
                # Use dedicated Qiskit methods for T1/T2 (legacy/compatibility)

                qubit_data[q_idx]["t1"] = properties.t1(q_idx)
                t1_relaxation_list.append((properties.t1(q_idx), q_idx))

                qubit_data[q_idx]["t2"] = properties.t2(q_idx)
                t2_dephasing_list.append((properties.t2(q_idx), q_idx))

            except Exception:
                # Catch exceptions if any specific property method fails
                pass

        # --- Readout Error and Duration ---
        if properties:
            try:
                # General readout error (single aggregated metric)
                readout_err = properties.readout_error(q_idx)
                qubit_data[q_idx]["readout_error"] = readout_err
                readout_errors_list.append(
                    (readout_err, q_idx)
                )  # Collect for overall average later

                # Readout Duration (readout_length)
                qubit_data[q_idx]["readout_length"] = properties.readout_length(q_idx)

                # Detailed readout probabilities (P(0|1) and P(1|0))
                p10_error = properties.qubit_property(q_idx, "prob_meas1_prep0")[0]
                qubit_data[q_idx]["p10"] = p10_error
                p10_error_list.append((p10_error, q_idx))

                p01_error = properties.qubit_property(q_idx, "prob_meas0_prep1")[0]
                qubit_data[q_idx]["p01"] = p01_error
                p01_error_list.append((p01_error, q_idx))

            except Exception:
                # Catch exceptions if any specific readout property fails
                pass

        # --- Single-Qubit Gate Errors (e.g., U, SX, RZ) ---
        if target:

            used_gates_on_q_idx = set()

            for instruction in transpiled_circuit.data:
                qargs = instruction.qubits
                op_name = instruction.operation.name

                # Check if it's a 1Q gate and if it involves the current physical qubit (q_idx)
                if len(qargs) == 1 and op_name not in EXCLUDE_GATES:
                    # Map the Qubit object to its physical index
                    q_index_used = transpiled_circuit.qubits.index(qargs[0])

                    if q_index_used == q_idx:
                        used_gates_on_q_idx.add(op_name)

            # We assume single-qubit gates are those with len=1 in the target
            for gate_name in used_gates_on_q_idx:
                gate_props = target.get(gate_name, {})

                # Check for single-qubit definitions
                # Qiskit stores InstProps in a dictionary keyed by qubit tuple (q_idx,)
                if (q_idx,) in gate_props:
                    inst_props = gate_props[(q_idx,)]

                    if inst_props.error is not None:
                        # Store error and duration for all relevant 1Q gates
                        key_err = f"{gate_name}_error"
                        key_dur = f"{gate_name}_duration"
                        qubit_data[q_idx][key_err] = inst_props.error
                        one_q_errors_list.append((inst_props.error, q_idx))
                        qubit_data[q_idx][key_dur] = inst_props.duration
                        one_q_duration_list.append((inst_props.duration, q_idx))

    results["qubit_properties"] = qubit_data

    # ------------------------------------------------------------
    # C. PER-LINK METRICS (Two-Qubit Gate Errors)
    # ------------------------------------------------------------
    link_data: Dict[Tuple[int, int], Dict[str, float]] = {}
    two_q_errors_list = []
    two_q_duration_list = []

    # Collect all unique two-qubit links used by the circuit
    used_links: set[Tuple[int, int]] = set()
    used_links = set(used_link_activity.keys())

    if target:
        for gate_name in results["basis_gates"]:
            gate_props = target.get(gate_name, {})
            # Check for two-qubit definitions in the target
            if len(target.get(gate_name, {}).keys()):  # Optimization
                for qarg_tuple, inst_props in gate_props.items():
                    if len(qarg_tuple) == 2 and inst_props is not None:
                        # Ensure link is in canonical form (sorted tuple)
                        canonical_link = tuple(sorted(qarg_tuple))

                        # Only collect metrics for links that were actually used
                        if canonical_link in used_links:
                            if canonical_link not in link_data:
                                link_data[canonical_link] = {}

                            if inst_props.error is not None:
                                key_err = f"{gate_name}_error"
                                link_data[canonical_link][key_err] = inst_props.error
                                two_q_errors_list.append(
                                    (inst_props.error, canonical_link)
                                )  # Collect for average
                            if inst_props.duration is not None:
                                key_dur = f"{gate_name}_duration"
                                link_data[canonical_link][key_dur] = inst_props.duration
                                two_q_duration_list.append(
                                    (inst_props.duration, canonical_link)
                                )

    results["link_properties"] = link_data

    # ------------------------------------------------------------
    # D. AGGREGATE METRICS (Averages for Noise Sensitivity)
    # ------------------------------------------------------------

    results["avg_readout_error"] = get_average_metric(readout_errors_list)
    results["avg_1q_error"] = get_average_metric(one_q_errors_list)
    results["avg_2q_error"] = get_average_metric(two_q_errors_list)
    results["avg_1q_duration"] = get_average_metric(one_q_duration_list)
    results["avg_2q_duration"] = get_average_metric(two_q_duration_list)
    results["avg_t1_time"] = get_average_metric(t1_relaxation_list)
    results["avg_t2_time"] = get_average_metric(t2_dephasing_list)
    results["avg_p10_error"] = get_average_metric(p10_error_list)
    results["avg_p01_error"] = get_average_metric(p01_error_list)

    # ------------------------------------------------------------
    # E. METRICS - Worst case (Worst Case for Noise Sensitivity)
    # ------------------------------------------------------------

    results["max_readout_error"], results["max_readout_qubit"] = get_worst_metric(
        readout_errors_list, find_max=True
    )
    results["max_1q_error"], results["max_1q_qubit"] = get_worst_metric(
        one_q_errors_list, find_max=True
    )
    results["max_2q_error"], results["max_2q_link"] = get_worst_metric(
        two_q_errors_list, find_max=True
    )
    results["max_p10_error"], results["max_p10_qubit"] = get_worst_metric(
        p10_error_list, find_max=True
    )
    results["max_p01_error"], results["max_p01_qubit"] = get_worst_metric(
        p01_error_list, find_max=True
    )

    # Durations (MAX duration)
    results["max_1q_duration"], results["max_1q_duration_qubit"] = get_worst_metric(
        one_q_duration_list, find_max=True
    )
    results["max_2q_duration"], results["max_2q_duration_link"] = get_worst_metric(
        two_q_duration_list, find_max=True
    )

    # Coherence Times (MIN time)
    results["min_t1_time"], results["min_t1_qubit"] = get_worst_metric(
        t1_relaxation_list, find_max=False
    )
    results["min_t2_time"], results["min_t2_qubit"] = get_worst_metric(
        t2_dephasing_list, find_max=False
    )

    return results
