# analytics/circuit_features.py

from qiskit import QuantumCircuit
from qiskit.circuit.library import (
    SwapGate,
)  # Import SwapGate for explicit identification


def extract_basic_features(circuit: QuantumCircuit) -> dict:
    """
    Extract basic circuit features from a Qiskit QuantumCircuit
    by analyzing instruction type and number of qubits acted upon.
    """
    features = {}

    # --- Core Metrics (use Qiskit built-in methods) ---
    features["tot_qubits"] = circuit.num_qubits
    features["qubits_used"] = len(circuit.layout.final_index_layout())
    features["depth"] = circuit.depth()
    features["size"] = circuit.size()

    # --- Gate Counts (Robust Counting) ---

    # Initialize robust counters
    num_1q_gates = 0
    num_2q_gates = 0

    # Full gate count dictionary (using Qiskit's built-in)
    gate_counts = circuit.count_ops()
    features["gate_counts"] = dict(gate_counts)

    # 1. Define non-unitary/non-computational operations to exclude from C_norm.
    EXCLUDE_OPS = ("barrier", "measure", "reset", "delay", "snapshot", "store")

    unitary_size = 0

    # Iterate through every instruction in the circuit data
    for instruction in circuit.data:
        # instruction is a CircuitInstruction(operation, qubits, clbits)
        op = instruction.operation
        qargs = instruction.qubits

        num_qargs = len(qargs)

        # 1. Identify 2-Qubit gates
        if num_qargs == 2:
            num_2q_gates += 1
            unitary_size += 1

        # 2. Identify 1-Qubit gates
        elif num_qargs == 1:
            # We generally ignore 'reset', 'measure' 'delay' or 'barrier' which might have 1 qarg
            # but usually have a dedicated op.name. For robust counting, we
            # only count standard unitary gates.
            if not op.name.startswith(EXCLUDE_OPS):
                num_1q_gates += 1
                unitary_size += 1

    norm_gate_dist = {}
    for op_name, count in gate_counts.items():
        if op_name not in EXCLUDE_OPS and unitary_size > 0:
            norm_gate_dist[op_name] = count / unitary_size

    features["norm_gate_dist"] = norm_gate_dist

    # --- Assign Final Robust Counts ---
    features["num_1q_gates"] = num_1q_gates
    features["num_2q_gates"] = num_2q_gates
    if (num_1q_gates + num_2q_gates) > 0:
        features["2q_gate_density"] = num_2q_gates / (num_1q_gates + num_2q_gates)
    else:
        features["2q_gate_density"] = 0.0
    features["num_measurements"] = gate_counts.get("measure", 0)

    return features
