# analytics/qubit_idling.py

from qiskit import QuantumCircuit
from qiskit.transpiler import Target
from qiskit.converters import circuit_to_dag
from qiskit.circuit import Delay, Qubit
from .backend_characterization import extract_backend_metrics
from adaptive_error_mitigation.utils import schedule_circuit_if_needed
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
    isa_qc: QuantumCircuit, backend
) -> Dict[int, Dict[str, float]]:
    """
    Returns qubit-wise T2 in dt, total post-init delay in dt, and delay/T2 ratio.

    Args:
        isa_qc: QuantumCircuit to analyze.
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

    # Ensure circuit is scheduled
    isa_qc_scheduled = schedule_circuit_if_needed(isa_qc, backend)

    backend_prop = extract_backend_metrics(isa_qc_scheduled, backend)

    # Extract T2 coherence times
    t2_map_sec = extract_t2_map_from_properties(backend_prop)

    # Commenting below section since the delay instruction is included while running schedule_circuit_if_needed
    # Convert to DAG to analyze ops
    # dag = circuit_to_dag(isa_qc_scheduled)
    # qubit_init_map = {q: False for q in isa_qc_scheduled.qubits}
    # delay_accumulator = {}

    # # Limit analysis to used qubits only
    # try:
    #     used_qubit_idxs = set(isa_qc_scheduled.layout.final_index_layout().keys())
    # except:
    #     used_qubit_idxs = set(
    #         i
    #         for i, q in enumerate(isa_qc_scheduled.qubits)
    #         if any(q in inst[1] for inst in isa_qc_scheduled.data)
    #     )

    # for node in dag.op_nodes():
    #     if len(node.qargs) != 1:
    #         continue  # Skip multi-qubit ops

    #     qubit = node.qargs[0]
    #     qidx = isa_qc_scheduled.qubits.index(qubit)
    #     if qidx not in used_qubit_idxs:
    #         continue

    #     if not isinstance(node.op, Delay):
    #         qubit_init_map[qubit] = True
    #         continue

    #     if not qubit_init_map[qubit]:
    #         continue  # Skip pre-init delays

    #     delay_accumulator[qidx] = max(delay_accumulator.get(qidx, 0), node.op.duration)

    # Accumulate delays per qubit directly from circuit data
    delay_accumulator = {}
    used_qubit_idxs = set()

    for inst in isa_qc_scheduled.data:
        for q in inst.qubits:
            qidx = isa_qc_scheduled.qubits.index(q)
            used_qubit_idxs.add(qidx)

            if inst.operation.name == "delay":
                delay_accumulator[qidx] = (
                    delay_accumulator.get(qidx, 0) + inst.operation.duration
                )

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
            "idle_dt": delay_dt,
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
                "idle_dt": delay_dt,
                # "ratio": round(ratio, 6),
                "decoher_err_prob": float(round(decoher_err_prob, 6)),
            }

    if processed_qubit_count == 0:
        avg_metrics = {
            "t2_dt": 0.0,
            "idle_dt": 0,
            # "ratio": 0.0,
            "decoher_err_prob": 0.0,
        }
    else:
        avg_metrics = {
            # Use sum() on the lists and divide by the count
            "t2_dt": round(sum(t2_dt_list) / processed_qubit_count, 2),
            "idle_dt": int(
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

def analyze_qubit_activity(circuit: QuantumCircuit, backend_target: Target):
    """
    Calculates sparsity (by layer and time) and gate distribution metrics
    for each qubit in a single pass over the circuit's DAG.
    
    Filters results to *only* include qubits that were used.
    
    A qubit's "lifespan" starts on its first operation and ends
    on its first measurement.
    
    Requires backend_target to get dt and gate durations.
    
    Returns:
        A dictionary:
        {
          'sparsity_by_layer': Dict[int, float],
          'sparsity_by_time': Dict[int, float],
          'distribution_mean_dt': Dict[int, float],
          'distribution_sd_dt': Dict[int, float]
        }
    
    Distribution Metrics (Mean/SD):
      - Mean/SD of the *time duration (dt)* of all idle blocks
        (sequences of '0's) in the qubit's lifespan.
      - Low Mean: Qubit is idle for short periods.
      - Low SD: Qubit is idle for very consistent/regular periods.
    """
    n_qubits = circuit.num_qubits
    if n_qubits == 0:
        return {'sparsity_by_layer': {}, 'sparsity_by_time': {}, 
                'distribution_mean_dt': {}, 'distribution_sd_dt': {}}

    # --- 1. Single DAG Conversion ---
    dag = circuit_to_dag(circuit)
    total_layers = dag.depth()
    
    if total_layers == 0:
        return {
            'sparsity_by_layer': {}, 'sparsity_by_time': {},
            'distribution_mean_dt': {}, 'distribution_sd_dt': {}
        }

    qubit_indices = {qubit: i for i, qubit in enumerate(circuit.qubits)}
    # 'delay' is now handled separately, but it's still an idle instruction
    IDLE_INSTRUCTIONS = {'barrier', 'delay'}

    try:
        inst_durations = backend_target.durations()
    except Exception as e:
        raise ValueError(f"Could not get durations from backend_target. Error: {e}")

    # --- 2. Initialize all state variables ---
    gate_count_layer = [0] * n_qubits
    lifespan_count_layer = [0] * n_qubits
    gate_duration_dt = [0.0] * n_qubits
    lifespan_duration_dt = [0.0] * n_qubits
    is_started = [False] * n_qubits
    is_measured = [False] * n_qubits
    current_idle_duration_dt = [0.0] * n_qubits
    idle_block_lists = [[] for _ in range(n_qubits)]

    # --- 3. Single Pass over all layers ---
    for layer_index, layer in enumerate(dag.layers()):
        gate_qubits_in_layer = set()
        measured_qubits_in_layer = set()
        max_duration_dt_this_layer = 0.0
        
        for op_node in layer['graph'].op_nodes():
            op = op_node.op
            q_indices = tuple(qubit_indices[q] for q in op_node.qargs)
            
            # --- FIX: Handle 'delay' and 'barrier' explicitly ---
            op_duration = 0.0
            if op.name == 'delay':
                # Get duration from the instruction itself
                if op.unit == 'dt':
                    op_duration = op.duration
                else:
                    # Convert from seconds to dt
                    op_duration = op.duration / backend_target.dt 
            elif op.name == 'barrier':
                op_duration = 0.0 # Barriers have zero duration
            else:
                # Only look up durations for actual gates
                op_duration = inst_durations.get(op.name, q_indices, unit='dt')
                if op_duration is None:
                    # Handle non-backend ops (e.g., reset, initialize)
                    op_duration = 0.0
            # --- END FIX ---
                
            max_duration_dt_this_layer = max(max_duration_dt_this_layer, op_duration)

            # --- (Rest of logic) ---
            op_qubits = [qubit_indices[q] for q in op_node.qargs]
            
            if op_node.name == 'measure':
                measured_qubits_in_layer.update(op_qubits)
            elif op_node.name not in IDLE_INSTRUCTIONS:
                gate_qubits_in_layer.update(op_qubits)
        
        started_qubits_in_layer = gate_qubits_in_layer.union(
            measured_qubits_in_layer
        )

        for i in range(n_qubits):
            if is_measured[i]:
                continue
            if not is_started[i]:
                if i in started_qubits_in_layer:
                    is_started[i] = True
                else:
                    continue
            
            lifespan_count_layer[i] += 1
            lifespan_duration_dt[i] += max_duration_dt_this_layer
            
            if i in gate_qubits_in_layer:
                gate_count_layer[i] += 1
                gate_duration_dt[i] += max_duration_dt_this_layer
                if current_idle_duration_dt[i] > 0:
                    idle_block_lists[i].append(current_idle_duration_dt[i])
                current_idle_duration_dt[i] = 0.0
            else:
                current_idle_duration_dt[i] += max_duration_dt_this_layer
            
            if i in measured_qubits_in_layer:
                is_measured[i] = True
                if current_idle_duration_dt[i] > 0:
                    idle_block_lists[i].append(current_idle_duration_dt[i])
                current_idle_duration_dt[i] = 0.0

    # --- 4. Final Calculation ---
    sparsity_layer_dict = {}
    sparsity_time_dict = {}
    distribution_mean_dict = {}
    distribution_sd_dict = {}
    
    for i in range(n_qubits):
        if not is_started[i]:
            continue
            
        # Add any trailing idle block (if qubit was idle at the end)
        if current_idle_duration_dt[i] > 0:
             idle_block_lists[i].append(current_idle_duration_dt[i])

        # --- Calculate Sparsity ---
        sparsity_layer_dict[i] = 1.0 - (gate_count_layer[i] / lifespan_count_layer[i])
        
        # Check for zero duration lifespan (e.g., a circuit with only barriers)
        if lifespan_duration_dt[i] == 0:
             sparsity_time_dict[i] = 1.0 # 0 gates / 0 time = 1.0 sparse
        else:
             sparsity_time_dict[i] = 1.0 - (gate_duration_dt[i] / lifespan_duration_dt[i])
        
        # --- Calculate Distribution Metrics ---
        idle_blocks = idle_block_lists[i]
        
        if not idle_blocks:
            distribution_mean_dict[i] = 0.0 # No idle periods
            distribution_sd_dict[i] = 0.0
        else:
            distribution_mean_dict[i] = round(np.mean(idle_blocks), 2)
            distribution_sd_dict[i] = round(np.std(idle_blocks), 2)
            
    return {
        'sparsity_by_layer': sparsity_layer_dict,
        'sparsity_by_time': sparsity_time_dict,
        'distribution_mean_dt': distribution_mean_dict,
        'distribution_sd_dt': distribution_sd_dict
    }