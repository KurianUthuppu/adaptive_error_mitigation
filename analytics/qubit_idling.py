# analytics/qubit_idling.py

from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from qiskit.circuit import Delay, Qubit
from typing import Dict, Any
import numpy as np


def extract_t2_map_from_properties(
    backend_properties: Dict[str, Any],
) -> Dict[int, float]:
    """Extracts T2 coherence times (in seconds) from backend property dictionary."""
    t2_data = {}
    qubit_props = backend_properties.get("qubit_properties", {})
    for qubit_index, props in qubit_props.items():
        t2 = props.get("t2", 0.0)
        if t2 > 0:
            t2_data[qubit_index] = t2
    return t2_data


def analyze_qubit_idling(
    qc: QuantumCircuit, backend_prop: Dict[str, Any], backend
) -> Dict[int, Dict[str, float]]:
    """
    Returns qubit-wise T2 in dt, total post-init delay in dt, and delay/T2 ratio.

    Args:
        qc: QuantumCircuit to analyze.
        backend_prop: Backend property dict (must include 'qubit_properties').
        backend: Qiskit backend instance (must support .target.dt).

    Returns:
        Dict of {qubit_index: {'t2_dt', 'delay_dt', 'ratio'}}
    """
    # Extract time resolution from backend
    try:
        dt_sec = backend.target.dt
    except AttributeError:
        raise ValueError("Backend does not provide 'target.dt' resolution.")

    # Extract T2 coherence times
    t2_map_sec = extract_t2_map_from_properties(backend_prop)

    # Convert to DAG to analyze ops
    dag = circuit_to_dag(qc)
    qubit_init_map = {q: False for q in qc.qubits}
    delay_accumulator = {}

    # Limit analysis to used qubits only
    try:
        used_qubit_idxs = set(qc.layout.final_index_layout().keys())
    except:
        used_qubit_idxs = set(
            i for i, q in enumerate(qc.qubits) if any(q in inst[1] for inst in qc.data)
        )

    for node in dag.op_nodes():
        if len(node.qargs) != 1:
            continue  # Skip multi-qubit ops

        qubit = node.qargs[0]
        qidx = qc.qubits.index(qubit)
        if qidx not in used_qubit_idxs:
            continue

        if not isinstance(node.op, Delay):
            qubit_init_map[qubit] = True
            continue

        if not qubit_init_map[qubit]:
            continue  # Skip pre-init delays

        delay_accumulator[qidx] = max(delay_accumulator.get(qidx, 0), node.op.duration)

    # Prepare results
    result = {}
    max_ratio_qubit_metrics = {}
    max_ratio = 0
    processed_qubit_count = 0
    t2_dt_list = []
    delay_dt_list = []

    for qidx in used_qubit_idxs:
        if qidx not in t2_map_sec:
            continue  # Skip if no T2 info

        t2_dt = t2_map_sec[qidx] / dt_sec
        delay_dt = delay_accumulator.get(qidx, 0)
        ratio = delay_dt / t2_dt if t2_dt > 0 else 0.0
        decoher_err_prob = 1 - np.exp(-delay_dt / t2_dt)
        processed_qubit_count += 1

        result[qidx] = {
            "t2_dt": round(t2_dt, 2),
            "max_delay_dt": delay_dt,
            # "ratio": round(ratio, 6),
            "decoher_err_prob": float(round(decoher_err_prob, 6)),
        }

        # Accumulate data for overall average calculation
        t2_dt_list.append(t2_dt)
        delay_dt_list.append(delay_dt)

        # Check for max ratio qubit
        if ratio > max_ratio:
            max_ratio = ratio
            max_ratio_qubit_metrics = {
                "qubit_idx": qidx,
                "t2_dt": round(t2_dt, 2),
                "max_delay_dt": delay_dt,
                # "ratio": round(ratio, 6),
                "decoher_err_prob": float(round(decoher_err_prob, 6)),
            }

    if processed_qubit_count == 0:
        avg_metrics = {
            "t2_dt": 0.0,
            "max_delay_dt": 0,
            # "ratio": 0.0,
            "decoher_err_prob": 0.0,
        }
    else:
        avg_metrics = {
            # Use sum() on the lists and divide by the count
            "t2_dt": round(sum(t2_dt_list) / processed_qubit_count, 2),
            "max_delay_dt": int(
                round(sum(delay_dt_list) / processed_qubit_count)
            ),  # Avg delay is often an integer unit
            # "ratio": round(sum(delay_dt_list) / sum(t2_dt_list), 6),
            "decoher_err_prob": float(
                round(1 - np.exp(-sum(delay_dt_list) / sum(t2_dt_list)), 6)
            ),
        }

    # 3. Return Final Result Structure
    return {
        "max_ratio_qubit": max_ratio_qubit_metrics,
        "overall_average": avg_metrics,
    }
