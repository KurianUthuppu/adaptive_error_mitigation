# analytics/layout_mapping.py

from qiskit import QuantumCircuit
from typing import Dict, List, Tuple, Union


def _analyze_physical_activity(circuit: QuantumCircuit) -> Dict[str, Dict]:
    """
    Analyzes activity on physical qubits and links based on the transpiled circuit.
    Assumes instruction qubit indices are already the final physical indices.
    """
    physical_qubit_activity: Dict[int, int] = {}
    physical_link_activity: Dict[Tuple[int, int], int] = {}

    # Operations to ignore for activity counting (structural/non-computational markers)
    IGNORE_OPS = ("barrier", "measure", "reset", "delay")

    for instruction in circuit.data:
        op = instruction.operation
        num_qubits = len(instruction.qubits)

        # Skip operations in the IGNORE list
        if op.name in IGNORE_OPS:
            continue

        # Get the integer index of the Qubit objects (assumed to be physical indices)
        physical_qargs = tuple(
            sorted([circuit.qubits.index(q) for q in instruction.qubits])
        )

        # --- Qubit Activity (1Q Gate Count ONLY) ---
        if num_qubits == 1:
            pq = physical_qargs[0]
            # Record ONLY the count of 1-qubit gates
            physical_qubit_activity[pq] = physical_qubit_activity.get(pq, 0) + 1

        # --- Link Activity (2Q Gate Count ONLY) ---
        elif num_qubits == 2:
            # Sort to ensure canonical representation for the link key
            link = tuple(sorted(physical_qargs))
            physical_link_activity[link] = physical_link_activity.get(link, 0) + 1

    return {
        "physical_qubit_activity": physical_qubit_activity,
        "physical_link_activity": physical_link_activity,
    }


def get_qubit_layout_mapping(
    transpiled_circuit: QuantumCircuit,
) -> Dict[str, Union[Dict[int, int], List[int], int, Dict]]:
    """
    Extracts layout mapping, list of used physical qubits, and activity analysis
    for a transpiled circuit.

    Args:
        transpiled_circuit (QuantumCircuit): The transpiled circuit containing layout information.

    Returns:
        Dict: A dictionary containing the mapping, used qubits, and activity analysis.
              Returns an empty dict if layout information is missing.
    """
    # 1. Ensure Layout Exists
    if not getattr(transpiled_circuit, "layout", None):
        return {}

    layout = transpiled_circuit.layout

    # 2. Retrieve Logical-to-Physical Map
    # final_index_layout is a list [physical_0, physical_1, ...] where index is logical qubit.
    l2p_list = layout.final_index_layout()
    # Convert to a clean dictionary {logical_idx: physical_idx}
    logical_to_physical_map = {l: p for l, p in enumerate(l2p_list) if p is not None}

    # 3. Extract Core Metrics
    physical_qubits_used = sorted(list(logical_to_physical_map.values()))

    # 4. Perform Activity Analysis (Critical Paths)
    # Renamed to a private helper with underscore: _analyze_physical_activity
    activity_metrics = _analyze_physical_activity(transpiled_circuit)

    # 5. Format Output
    results = {
        "logical_to_physical_map": logical_to_physical_map,
        "physical_qubits_used": physical_qubits_used,
        "num_physical_qubits_used": len(physical_qubits_used),
        # Activity (gate count) on each physical qubit
        "physical_qubit_activity": activity_metrics["physical_qubit_activity"],
        # Activity (2Q gate count) on each physical link (critical paths)
        "physical_link_activity": activity_metrics["physical_link_activity"],
    }

    return results
