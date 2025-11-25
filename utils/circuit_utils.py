# adaptive_error_mitigation/utils/circuit_utils.py

from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import ALAPScheduleAnalysis
from .color_log import ANSI


def schedule_circuit_if_needed(circuit: QuantumCircuit, backend) -> QuantumCircuit:
    """
    Check if circuit is scheduled; if not, apply ALAP scheduling.

    Args:
        circuit: Input quantum circuit
        backend: Backend object for instruction durations

    Returns:
        Scheduled quantum circuit
    """
    if circuit.duration is None:
        print(
            f"\n{ANSI.BOLD}---> Circuit not scheduled. Applying ALAP scheduling...{ANSI.RESET}"
        )
        schedule_pm = PassManager([ALAPScheduleAnalysis(backend.instruction_durations)])
        return schedule_pm.run(circuit)
    else:
        print(
            f"\n{ANSI.BOLD}---> Circuit already scheduled (duration: {circuit.duration}).{ANSI.RESET}"
        )
        return circuit
