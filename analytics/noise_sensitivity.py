# analytics/noise_sensitivity.py

from qiskit import QuantumCircuit
from qiskit.providers import Backend
from typing import Dict, Any, Tuple
import numpy as np
from .layout_mapping import get_qubit_layout_mapping
from .backend_characterization import extract_backend_metrics


def calculate_derived_noise_metrics(
    transpiled_circuit: QuantumCircuit, backend: Backend
) -> Dict[str, Any]:
    """
    Combines circuit activity and hardware properties to generate derived noise metrics,
    using pre-calculated averages from the hardware data.

    Args:
        transpiled_circuit (QuantumCircuit): The circuit after mapping to the backend.
        backend (Backend): The target quantum hardware backend.
        layout_data (Dict): Output from get_qubit_layout_mapping, containing
                            'physical_qubits_used' and 'logical_to_physical_map'.

    Returns:
        Dict: A comprehensive dictionary of calibration data.
    """

    layout_data = get_qubit_layout_mapping(transpiled_circuit)
    backend_data = extract_backend_metrics(transpiled_circuit, backend)

    results: Dict[str, Any] = {}

    # 1. Input Data Extraction
    qubit_activity = layout_data.get("physical_qubit_activity", {})
    link_activity = layout_data.get("physical_link_activity", {})

    qubit_props = backend_data.get("qubit_properties", {})
    link_props = backend_data.get("link_properties", {})
    coupling_map_size = backend_data.get("coupling_map_size", [])

    # ------------------------------------------------------------
    # 2. Aggregated Metrics (Consume Pre-calculated Averages)
    # ------------------------------------------------------------

    # NOTE: These averages are assumed to be computed in the hardware_characterization module
    # and placed into the hardware_data dictionary via the _calculate_average_errors helper.
    results["avg_2q_error"] = backend_data.get("avg_2q_error", 0.0)
    results["avg_readout_error"] = backend_data.get("avg_readout_error", 0.0)

    # ------------------------------------------------------------
    # 3. Connectivity Stress (Derived Feature)
    # ------------------------------------------------------------

    # Definition: The fraction of available physical links (edges) that are utilized.
    used_links_count = len(link_activity)
    results["connectivity_stress"] = _calculate_connectivity_stress(
        used_links_count, coupling_map_size
    )

    # ------------------------------------------------------------
    # 4. Noise Sensitivity Score (Derived Feature)
    # ------------------------------------------------------------

    noise_sensitivity, qubit_sensitivity, link_sensitivity = (
        _calculate_noise_sensitivity(
            qubit_activity, link_activity, qubit_props, link_props
        )
    )
    results["overall_noise_sensitivity"] = noise_sensitivity

    # ------------------------------------------------------------
    # 5. Noise Hotspots (Derived Feature)
    # ------------------------------------------------------------

    # Hotspots are the qubits/links with the highest activity * weighted error score
    hotspots = _identify_noise_hotspots(qubit_sensitivity, link_sensitivity)
    results["noise_hotspots"] = hotspots

    return results


# =========================================================================
# HELPER FUNCTIONS (Remains the same as before, providing the logic for the derived features)
# =========================================================================


def _calculate_connectivity_stress(
    used_links_count: int, coupling_map_size: int
) -> float:
    """
    Calculates Connectivity Stress.
    Definition: Ratio of unique utilized physical links to the total available physical links.
    """
    if coupling_map_size == 0:
        return 0.0

    # Note: Qiskit's coupling map is a list of pairs (edges), so its length is the total available edges.
    return float(used_links_count / coupling_map_size)


def _calculate_noise_sensitivity(
    qubit_activity: Dict[int, int],
    link_activity: Dict[Tuple[int, int], int],
    qubit_props: Dict,
    link_props: Dict,
) -> Tuple[float, Dict, Dict]:
    """
    Calculates the overall Noise Sensitivity Score and sensitivity per component.

    Sensitivity (Component) = Activity * Max_Error_Rate + Activity / T_Coherence
    """
    qubit_sensitivity: Dict[int, float] = {}
    link_sensitivity: Dict[Tuple[int, int], float] = {}
    total_sensitivity = 0.0

    # --- 1. Qubit Sensitivity (Decoherence + 1Q Error) ---
    for q_idx, activity in qubit_activity.items():
        props = qubit_props.get(q_idx, {})

        # Calculate the AVERAGE relevant single-qubit error for the used 1Q gates
        one_q_errors = []

        for key, value in props.items():
            # Filter for keys ending in '_error' that are NOT readout error (which is handled separately)
            if (
                key.endswith("_error")
                and "readout" not in key
                and value is not None
                and value >= 0
            ):
                one_q_errors.append(value)

        # Calculate the average 1Q error rate for this specific qubit
        # Use 0.0 as a fallback if no errors are found (e.g., if only 'delay' was used)
        avg_1q_error = sum(one_q_errors) / len(one_q_errors) if one_q_errors else 0.0

        # Risk = (Activity * Max_Error_Rate) + (Activity / Coherence_Time)
        gate_1q_risk = activity * avg_1q_error

        qubit_sensitivity[q_idx] = float(gate_1q_risk)
        total_sensitivity += gate_1q_risk

    # --- 2. Link Sensitivity (2Q Gate Error) ---
    for link, activity in link_activity.items():
        props = link_props.get(link, {})

        # Calculate the AVERAGE relevant two-qubit error for the link
        two_q_errors = []
        for key, value in props.items():
            # Filter for keys ending in '_error'
            if key.endswith("_error") and value is not None and value >= 0:
                two_q_errors.append(value)

        # Calculate the average 2Q error rate for this specific link
        avg_2q_error = sum(two_q_errors) / len(two_q_errors) if two_q_errors else 0.0

        # Link Risk = Activity * Max_2Q_Error
        gate_2q_risk = activity * avg_2q_error
        link_sensitivity[link] = float(gate_2q_risk)
        total_sensitivity += gate_2q_risk

    return float(total_sensitivity), qubit_sensitivity, link_sensitivity


def _identify_noise_hotspots(qubit_sensitivity: Dict, link_sensitivity: Dict) -> Dict:
    """
    Identifies sensitive qubits and links based on a statistical threshold (Mean + 1.5 * StdDev)
    rather than a fixed 'Top N'.
    """

    # 1. Prepare Scores for Statistical Analysis
    qubit_scores = list(qubit_sensitivity.values())
    link_scores = list(link_sensitivity.values())

    # Initialize thresholds and calculate statistics
    qubit_threshold = 0.0
    link_threshold = 0.0

    # 2. Calculate Dynamic Threshold for Qubits
    if qubit_scores:
        # Use a statistical threshold: Mean + 1.5 * Standard Deviation
        mean_q_score = np.mean(qubit_scores)
        std_q_score = np.std(qubit_scores)
        qubit_threshold = float(mean_q_score + (1 * std_q_score))

    # 3. Calculate Dynamic Threshold for Links
    if link_scores:
        # Use a statistical threshold: Mean + 1.5 * Standard Deviation
        mean_l_score = np.mean(link_scores)
        std_l_score = np.std(link_scores)
        link_threshold = float(mean_l_score + (1 * std_l_score))

    # 4. Identify Hotspots (Qubits)
    hotspot_qubits = [
        q_idx
        for q_idx, score in qubit_sensitivity.items()
        if score >= qubit_threshold  # Include scores exactly at the threshold
    ]

    # 5. Identify Hotspots (Links)
    hotspot_links = [
        link
        for link, score in link_sensitivity.items()
        if score >= link_threshold  # Include scores exactly at the threshold
    ]

    return {"qubits": hotspot_qubits, "pairs": hotspot_links}
