# adaptive_error_mitigation/primitives/adaptive_estimator.py

from qiskit_ibm_runtime import Estimator
from typing import List, Union, Tuple, TYPE_CHECKING
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

# Import the decision engine
from adaptive_error_mitigation.mitigation import (
    select_mitigation_options,
)

# Define a specific type for the expected input (circuit, observable)
PubType = Tuple[QuantumCircuit, SparsePauliOp]


def run(pubs: List[PubType], backend, shots: int = None, **kwargs):
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
    # 1. Input Validation (Constraint 1)
    if not isinstance(pubs, list) or len(pubs) != 1:
        # Give the required warning/error message for the constraint
        raise ValueError(
            "Input constraint violation: 'pubs' must be a list containing exactly one transpiled circuit and applied observable (isa_qc, isa_observable) tuple. "
            "The adaptive framework sets options based on a single transpiled circuit/backend pair."
        )

    # Extract the single circuit and observable
    isa_qc, isa_observable = pubs[0]

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
    estimator = Estimator(mode=backend, options=estimator_options, **kwargs)

    # Run the job with only the required single pub (Constraint 3)
    job = estimator.run([(final_circuit, isa_observable)])

    return job
