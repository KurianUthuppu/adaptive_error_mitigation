# adaptive_error_mitigation/mitigation/strategies/dd_strategy.py

# Import the configuration constants from the top-level config file
from adaptive_error_mitigation import config
from adaptive_error_mitigation.utils import ANSI, colorize

from qiskit.transpiler import PassManager
from qiskit.transpiler.passes import PadDynamicalDecoupling, ALAPScheduleAnalysis
from qiskit.circuit import QuantumCircuit
from qiskit.circuit.library import XGate


def _dynamical_decoupling_preprocess(
    isa_qc: QuantumCircuit, backend, dd_sequence
) -> QuantumCircuit:
    """Apply dynamical decoupling to the input circuit.

    Args:
        isa_qc (QuantumCircuit): Input circuit to run error mitigation on.
        backend: Backend object providing instruction_durations.
        dd_sequence: Sequence of gates for DD (e.g., [XGate(), XGate()]).

    Returns:
        QuantumCircuit: Circuit with dynamic decoupling applied.
    """
    dd_pm = PassManager(
        [
            ALAPScheduleAnalysis(target=backend.target),
            PadDynamicalDecoupling(target=backend.target, dd_sequence=dd_sequence),
        ]
    )
    return dd_pm.run(isa_qc)


def get_dd_options(
    crk_density: float,
    backend,
    isa_qc: QuantumCircuit,
) -> dict:
    """
    Applies the adaptive heuristic for Dynamic Decoupling (DD),
    determining if DD should be enabled based on the backend's
    maximum decoherence error probability.

    Args:
        max_decoher_err_prob: The maximum decoherence error probability from the backend.
        max_dd_qubit: The qubit index with maximum decoherence error.
        backend: Backend object for instruction durations.
        isa_qc: The ISA-level quantum circuit to potentially apply DD on.

    Returns:
        A dictionary containing 'dynamical_decoupling' settings and
        optionally the preprocessed circuit.
    """

    # Use the threshold and DD sequence from the imported config file
    DD_MIN_CD_THRESHOLD = config.DD_MIN_CD_THRESHOLD
    DD_MAX_CD_THRESHOLD = config.DD_MAX_CD_THRESHOLD
    DD_SEQUENCE = [XGate(), XGate()]

    dd_circuit = None

    # Default DD settings (disabled)
    dd_options = {"dynamical_decoupling": {"enable": False}}

    # Preserve original layout before DD pass
    original_layout = isa_qc._layout

    if DD_MIN_CD_THRESHOLD <= crk_density <= DD_MAX_CD_THRESHOLD:
        # Apply ANSI coloring for highlighting and clarity
        metric_val = colorize(f"{crk_density:.4f}", ANSI.B_YELLOW)
        min_val = colorize(f"{DD_MIN_CD_THRESHOLD:.4f}", ANSI.B_CYAN)
        max_val = colorize(f"{DD_MAX_CD_THRESHOLD:.4f}", ANSI.B_CYAN)

        action_mitigation = colorize("Dynamic Decoupling (DD)", ANSI.B_GREEN)

        # Format DD_SEQUENCE for display
        dd_seq_str = colorize(f"{[gate.name for gate in DD_SEQUENCE]}", ANSI.CYAN)

        print(
            f"\n{ANSI.BOLD}---> HEURISTIC TRIGGERED:{ANSI.RESET} Circuit density Within Range\n"
            f"     | Metric: CIRCUIT DENSITY (CD) - {metric_val}\n"
            f"     | Threshold Range: [{min_val}, {max_val}] (config.py)\n"
            f"{ANSI.BOLD}---> ACTION TAKEN:{ANSI.RESET} ENABLED {action_mitigation}\n"
            f"     | Sequence Applied: {dd_seq_str}"
        )

        # Apply DD preprocessing to the circuit
        dd_circuit = _dynamical_decoupling_preprocess(isa_qc, backend, DD_SEQUENCE)

        # Restore layout after DD pass
        dd_circuit._layout = original_layout

    # Return DD options and optionally the preprocessed circuit
    return {
        "dd_options": dd_options,
        "dd_circuit": dd_circuit,
    }
