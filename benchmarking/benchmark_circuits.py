import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.transpiler import generate_preset_pass_manager, PassManager
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDynamicalDecoupling
from qiskit.circuit.library import XGate
from qiskit.quantum_info import SparsePauliOp
from adaptive_error_mitigation.utils import schedule_circuit_if_needed

def dynamical_decoupling_preprocess(
    input_circuit: QuantumCircuit, backend
) -> QuantumCircuit:
    """Apply dynamical decoupling to the input circuit.

    Args:
        input_circuit (QuantumCircuit): input circuit to run error mitigation on.
    """
    DD_SEQUENCE = [XGate(), XGate()]

    DD_PM = PassManager(
        [
            ALAPScheduleAnalysis(backend.instruction_durations),
            PadDynamicalDecoupling(
                durations=backend.instruction_durations, dd_sequence=DD_SEQUENCE
            ),
        ]
    )
    return DD_PM.run(input_circuit)

# Dynamical Decoupling
def dd_benchmark_circuit(NUM_QUBITS, backend):
    qc = QuantumCircuit(NUM_QUBITS)

    # Apply Hadamard gate to first qubit to create superposition
    qc.h(0)

    # Create entanglement chain using CNOT gates
    for i in range(NUM_QUBITS - 1):
        qc.cx(i, i + 1)

    pauli_string = "Z" * NUM_QUBITS


    pm_lvl3 = generate_preset_pass_manager(
        optimization_level=3, seed_transpiler=42, backend=backend, scheduling_method="alap"
    )
    isa_qc = pm_lvl3.run(qc)
    isa_qc = schedule_circuit_if_needed(isa_qc, backend)
    
    # The observable is then created from this string
    observable = SparsePauliOp(pauli_string)
    isa_observable = observable.apply_layout(isa_qc.layout)

    dd_circ_measured = dynamical_decoupling_preprocess(isa_qc, backend)

    return isa_qc, dd_circ_measured, isa_observable

def zne_benchmark_circuit(NUM_QUBITS, backend):
    # Create GHZ state
    ghz = QuantumCircuit(NUM_QUBITS)
    ghz.h(0)
    for i in range(NUM_QUBITS - 1):
        ghz.cx(i, i + 1)

    # Loschmidt echo circuit: GHZ → barrier → GHZ† → measurement
    echo = QuantumCircuit(NUM_QUBITS)
    echo.compose(ghz, inplace=True)
    echo.barrier()
    echo.compose(ghz.inverse(), inplace=True)
    echo.x(range(NUM_QUBITS))

    pm_lvl3 = generate_preset_pass_manager(
        optimization_level=3,
        seed_transpiler=42,
        backend=backend,
        scheduling_method="alap",
    )

    isa_qc = pm_lvl3.run(echo)    
    pauli_string = "Z" * NUM_QUBITS
    observable = SparsePauliOp(pauli_string)
    isa_observable = observable.apply_layout(isa_qc.layout)

    return isa_qc, isa_observable