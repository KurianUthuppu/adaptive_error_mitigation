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
    features["num_qubits"] = circuit.num_qubits
    features["depth"] = circuit.depth()
    features["size"] = circuit.size()

    # --- Gate Counts (Robust Counting) ---

    # Initialize robust counters
    num_1q_gates = 0
    num_2q_gates = 0

    # Full gate count dictionary (using Qiskit's built-in)
    gate_counts = circuit.count_ops()
    features["gate_counts"] = dict(gate_counts)

    # Iterate through every instruction in the circuit data
    for instruction in circuit.data:
        # instruction is a CircuitInstruction(operation, qubits, clbits)
        op = instruction.operation
        qargs = instruction.qubits

        num_qargs = len(qargs)

        # 1. Identify 2-Qubit gates
        if num_qargs == 2:
            # We filter out 'swap' here to ensure it is only counted once
            # Note: A SWAP is intrinsically a 2-qubit gate, but we often track
            # it separately due to its role as a routing overhead indicator.
            if op.name != "swap":
                num_2q_gates += 1

        # 2. Identify 1-Qubit gates
        elif num_qargs == 1:
            # We generally ignore 'delay' or 'barrier' which might have 1 qarg
            # but usually have a dedicated op.name. For robust counting, we
            # only count standard gates.
            if not op.name.startswith(("barrier", "measure", "reset", "delay")):
                num_1q_gates += 1

    # --- Assign Final Robust Counts ---
    features["num_1q_gates"] = num_1q_gates
    features["num_2q_gates"] = num_2q_gates
    features["num_measurements"] = gate_counts.get("measure", 0)

    return features
