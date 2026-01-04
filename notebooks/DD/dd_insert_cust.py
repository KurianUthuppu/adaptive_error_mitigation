from typing import Dict, List, Any, Set
from qiskit import QuantumCircuit
from qiskit.circuit import Instruction, Delay, Qubit
from qiskit.converters import circuit_to_dag, dag_to_circuit
from adaptive_error_mitigation.analytics import extract_backend_metrics
from adaptive_error_mitigation.utils import schedule_circuit_if_needed
import numpy as np


def extract_t2_map_from_properties(
    backend_properties: Dict[str, Any],
) -> Dict[int, float]:
    """
    Extracts T2 coherence times from a backend properties dictionary.

    Args:
        backend_properties: A dictionary containing backend configuration,
                            including the 'qubit_properties' structure.

    Returns:
        A dictionary mapping physical qubit index (int) to T2 time (float) in seconds.
    """
    t2_data = {}
    qubit_props = backend_properties.get("qubit_properties", {})

    for qubit_index, properties in qubit_props.items():
        t2_time = properties.get("t2", 0.0)
        if t2_time > 0:
            t2_data[qubit_index] = t2_time

    return t2_data


class ExecutionConfig:
    """
    Stores configuration required for dynamical decoupling execution.
    Automatically extracts T2 map from backend properties.
    """

    def __init__(
        self,
        isa_qc: QuantumCircuit,
        backend: Any,
        dd_sequence_base: List[Instruction],
        t2_threshold_ratio: float = 0.001,
    ):
        """
        Initialize execution configuration for DD.

        Args:
            backend_prop: Dictionary of backend metrics (includes qubit_properties).
            isa_qc: Input Qiskit circuit (ISA-level circuit).
            backend: Target backend object from Qiskit.
            dd_sequence_base: List of base DD gates (e.g., [XGate(), XGate()]).
            t2_threshold_ratio: Minimum T_idle/T2 ratio for applying DD.
        """
        backend_prop = extract_backend_metrics(isa_qc, backend)
        self.t2_map = extract_t2_map_from_properties(backend_prop)
        # Ensure circuit is scheduled
        isa_qc_scheduled = schedule_circuit_if_needed(isa_qc, backend)
        self.isa_qc = isa_qc_scheduled
        self.backend = backend
        self.dd_sequence_base = dd_sequence_base
        self.t2_threshold_ratio = t2_threshold_ratio

        try:
            self.target = backend.target
            self.dt_sec = self.target.dt
            self.min_sequence_length = len(dd_sequence_base)
        except AttributeError as e:
            raise ValueError(
                f"Backend missing required attributes: {e}. "
                "Ensure 'backend.target' and 'backend.target.dt' exist."
            ) from e


class DynamicalDecoupler:
    """
    Responsible for inserting Dynamical Decoupling (DD) sequences
    into delays within the input quantum circuit.
    """

    def __init__(self, config: ExecutionConfig):
        self.config = config

    def _calculate_dd_pulses(self, qubit_index: int, T_idle_dt: int) -> int:
        cfg = self.config
        Q_T2_sec = cfg.t2_map[qubit_index]
        Q_T2_dt = Q_T2_sec / cfg.dt_sec
        decoh_ratio = 1 - np.exp(-T_idle_dt / Q_T2_dt)

        if decoh_ratio < cfg.t2_threshold_ratio:
            return None

        dd_props = cfg.target.get("x", {}).get((qubit_index,), None)
        if dd_props is None:
            return None

        dd_pulse_duration_dt = round(dd_props.duration / cfg.dt_sec)
        dd_pulse_error = dd_props.error

        D_min_delay = 1
        n_pi = 0

        while True:
            n_pi_candidate = n_pi + cfg.min_sequence_length
            total_time_needed = (n_pi_candidate * dd_pulse_duration_dt) + (
                (3 * n_pi_candidate + 1) * D_min_delay
            )
            tot_gate_err = n_pi_candidate * dd_pulse_error
            decoher_err_prob = 1 - np.exp(
                -T_idle_dt / ((4 * n_pi_candidate + 1) * Q_T2_dt)
            )

            if (
                total_time_needed > T_idle_dt
                or tot_gate_err >= 2 * decoher_err_prob
                or n_pi_candidate > 2
            ):
                break

            n_pi = n_pi_candidate

        return n_pi if n_pi > 0 else None

    def _create_replacement_circuit(
        self, n_pi: int, T_idle_dt: int, dd_pulse_duration_dt: int, qubit
    ) -> QuantumCircuit:
        cfg = self.config
        total_pulse_time_dt = n_pi * dd_pulse_duration_dt
        tau_total_dt = T_idle_dt - total_pulse_time_dt
        num_intervals = n_pi

        tau_dt = tau_total_dt // num_intervals
        half_tau_dt = tau_dt // 2
        remainder_dt = tau_total_dt % num_intervals
        initial_slack = remainder_dt // 2
        final_slack = remainder_dt - initial_slack

        replacement_qc = QuantumCircuit(1)
        target_wire = replacement_qc.qubits[0]

        replacement_qc.delay(half_tau_dt + initial_slack, [target_wire], unit="dt")

        for i in range(n_pi):
            pulse = cfg.dd_sequence_base[i % len(cfg.dd_sequence_base)]
            replacement_qc.append(pulse, [target_wire])
            if i < n_pi - 1:
                replacement_qc.delay(tau_dt, [target_wire], unit="dt")

        replacement_qc.delay(half_tau_dt + final_slack, [target_wire], unit="dt")
        return replacement_qc

    def run(self) -> QuantumCircuit:
        cfg = self.config
        dag_to_process = circuit_to_dag(cfg.isa_qc)
        qubits_initialized: Set[Qubit] = set()

        for node in dag_to_process.op_nodes():
            instruction = node.op
            if len(node.qargs) != 1:
                continue

            qubit = node.qargs[0]
            qubit_index = dag_to_process.qubits.index(qubit)

            if not isinstance(instruction, Delay):
                qubits_initialized.add(qubit)
                continue

            if qubit not in qubits_initialized:
                continue

            if qubit_index not in cfg.t2_map:
                continue

            T_idle_dt = instruction.duration
            n_pi = self._calculate_dd_pulses(qubit_index, T_idle_dt)
            if n_pi is None:
                continue

            dd_props = cfg.target.get("x", {}).get((qubit_index,), None)
            dd_pulse_duration_dt = round(dd_props.duration / cfg.dt_sec)

            replacement_qc = self._create_replacement_circuit(
                n_pi, T_idle_dt, dd_pulse_duration_dt, qubit
            )

            dag_to_process.substitute_node_with_dag(
                node, circuit_to_dag(replacement_qc)
            )

        # Generate the new circuit from the DAG
        new_qc = dag_to_circuit(dag_to_process)

        # Use the internal attribute '_layout' to bypass the read-only restriction
        if hasattr(cfg.isa_qc, "layout"):
            new_qc._layout = cfg.isa_qc.layout

        return new_qc
