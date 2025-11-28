# adaptive_error_mitigation/utils/isa_qc_utils.py

from qiskit import QuantumCircuit
from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDelay, RemoveBarriers
from .color_log import ANSI


def print_scheduled_status(isa_qc, backend):
    """
    Checks the circuit for existing delay instructions and prints its scheduling status.

    If the circuit contains delays, it calculates and displays the estimated duration
    using the backend's target. Otherwise, it indicates that scheduling is pending.

    Args:
        isa_qc (QuantumCircuit): The input ISA quantum circuit to inspect.
        backend (Backend): The backend object, required for duration estimation.
    """
    if any(inst.operation.name == "delay" for inst in isa_qc.data):
        crkt_duration = isa_qc.estimate_duration(backend.target)
        print(
            f"\n{ANSI.BOLD}---> Circuit already scheduled (duration: {crkt_duration}).{ANSI.RESET}"
        )
    else:
        print(
            f"\n{ANSI.BOLD}---> Circuit not scheduled. Applying ALAP scheduling...{ANSI.RESET}"
        )


def _is_scheduled(isa_qc):
    """
    Determines if the circuit has likely been scheduled by checking for delay operations.

    Args:
        isa_qc (QuantumCircuit): The quantum circuit to check.

    Returns:
        bool: True if 'delay' instructions are present, False otherwise.
    """
    return any(inst.operation.name == "delay" for inst in isa_qc.data)


def schedule_circuit_if_needed(isa_qc: QuantumCircuit, backend) -> QuantumCircuit:
    """
    Check if isa_qc is scheduled; if not, apply ALAP scheduling.

    Args:
        isa_qc: Input quantum isa_qc
        backend: Backend object for instruction duration

    Returns:
        Scheduled quantum isa_qc
    """
    original_layout = isa_qc.layout
    target = backend.target
    if _is_scheduled(isa_qc):
        return isa_qc
    else:
        schedule_pm = PassManager(
            [
                ALAPScheduleAnalysis(target=target),
                PadDelay(target=target),
            ]
        )

        scheduled_crkt = schedule_pm.run(isa_qc)

        # Restore layout
        scheduled_crkt._layout = original_layout

        return scheduled_crkt
