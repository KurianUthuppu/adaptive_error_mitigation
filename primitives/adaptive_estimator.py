# adaptive_error_mitigation/primitives/adaptive_estimator.py

from qiskit_ibm_runtime import Estimator
from typing import List, Union, Tuple, TYPE_CHECKING
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.controlflow import ControlFlowOp

# Import the decision engine
from adaptive_error_mitigation.mitigation import (
    select_mitigation_options,
)

# Define a specific type for the expected input (circuit, observable)
PubType = Tuple[QuantumCircuit, SparsePauliOp]


def run(pubs: List[PubType], backend, mode=None, shots: int = None, **kwargs):
    """
    Runs the Estimator with options adaptively determined by heuristics.

    CRITICAL: This function requires exactly one publication (circuit, observable)
    as input, as heuristics are set per circuit/backend pair.

    Args:
        pubs: A list containing exactly one (circuit, observable) tuple.
        backend: The Qiskit Backend object to use for execution.
        **kwargs: Additional keyword arguments passed to the Estimator constructor.

    Returns:
        The Qiskit Runtime Job object.
    """

    # 1. Initialize a list to hold the results for ALL circuits
    batch_results = []

    for i, (isa_qc, isa_observable) in enumerate(pubs):

        print(f"\n--- Processing Pub {i+1}/{len(pubs)} ---")

        # --- DYNAMIC CIRCUIT CHECK ---
        is_dynamic = any(
            isinstance(inst.operation, ControlFlowOp) for inst in isa_qc.data
        )

        if is_dynamic:
            print(
                f"\n[!] SKIP: Pub {i+1} contains Dynamic Control Flow (if_test/loops)."
            )
            print(
                "The Adaptive Estimator framework does not currently support dynamic circuits."
            )
            # Depending on your needs, you can 'continue' to skip or 'break' to stop everything.
            batch_results.append(
                {"job": None, "error": "Dynamic circuit not supported"}
            )
            continue

        # 2. Determine Adaptive Estimator Options (Constraint 2)
        print("--- Initiating Adaptive Error Mitigation and Suppression Framework ---")
        mitigation_result = select_mitigation_options(
            isa_qc, backend, shots
        )  # Updated signature

        # Extract final options and circuit from the result
        estimator_options = mitigation_result["final_options"]
        final_circuit = mitigation_result["final_circuit"]
        print(
            "\n--- Optimal Error Mitigation & Suppression Techniques applied in Estimator Options ---\n"
        )

        print(
            f"--- Submitting job to {backend.name} with configured EstimatorOptions ---\n"
        )

        # 3. Initialize and Run the Estimator (Constraint 3 & **kwargs)
        # The **kwargs are passed through here
        exec_mode = mode if mode is not None else backend
        estimator = Estimator(mode=exec_mode, options=estimator_options, **kwargs)

        # Run the job with only the required single pub (Constraint 3)
        job = estimator.run([(final_circuit, isa_observable)])
        # job = f"job_id_adapt_est_itr{i}"
        batch_results.append({"job": job, "est_options": estimator_options})

    return batch_results
