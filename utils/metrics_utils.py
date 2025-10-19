from typing import Dict, Union, List
import numpy as np


def _get_probability_vector(
    counts: Dict[str, int], shots: int, all_states: List[str]
) -> np.ndarray:
    """
    Converts raw experimental measurement counts into a probability distribution vector,
    ordered based on the provided list of all possible quantum states.

    Args:
        counts (Dict[str, int]): Measured frequency of each state from quantum experiment.
        shots (int): Total number of measurement shots.
        all_states (List[str]): List of all possible states in lexicographical order.

    Returns:
        np.ndarray: Ordered probability vector corresponding to `all_states`.
    """
    if shots == 0:
        return np.zeros(len(all_states))

    return np.array([counts.get(state, 0) / shots for state in all_states])


def _get_all_possible_states(num_qubits: int) -> List[str]:
    """
    Generates all possible quantum basis states (bitstrings) for a given number of qubits.

    Args:
        num_qubits (int): Number of qubits.

    Returns:
        List[str]: List of 2^num_qubits bitstrings in lexicographical order.
    """
    return [format(i, f"0{num_qubits}b") for i in range(2**num_qubits)]


def cal_em_eff_sampler(
    counts_no_em: Dict[str, int],
    counts_em: Dict[str, int],
    ideal_counts: Dict[str, int],
    num_qubits: int,
) -> Dict[str, Union[float, int]]:
    """
    Computes the efficacy of error mitigation using Total Variation Distance (TVD)
    and Target State Population metrics, based on raw count data received from Sampler primitive.

    Args:
        counts_no_em (Dict[str, int]): Raw counts without error mitigation.
        counts_em (Dict[str, int]): Raw counts with error mitigation.
        ideal_counts (Dict[str, int]): Ideal theoretical outcome counts.
        num_qubits (int): Number of qubits involved.

    Returns:
        Dict[str, Union[float, int]]: Dictionary of metrics including TVD values,
        population measures, and percentage improvements.
    """
    if num_qubits <= 0:
        return {"error": "Invalid num_qubits."}

    N_SHOTS_IDEAL = sum(ideal_counts.values())
    N_SHOTS_NO_EM = sum(counts_no_em.values())
    N_SHOTS_EM = sum(counts_em.values())

    if N_SHOTS_IDEAL == 0 or N_SHOTS_NO_EM == 0 or N_SHOTS_EM == 0:
        return {"error": "One or more count dictionaries resulted in zero total shots."}

    all_states = _get_all_possible_states(num_qubits)

    # Identify target states as those with non-zero probability in the ideal case
    target_states = [
        state.zfill(num_qubits) for state, count in ideal_counts.items() if count > 0
    ]

    P_ideal = _get_probability_vector(ideal_counts, N_SHOTS_IDEAL, all_states)
    P_nodd = _get_probability_vector(counts_no_em, N_SHOTS_NO_EM, all_states)
    P_dd = _get_probability_vector(counts_em, N_SHOTS_EM, all_states)

    # Total Variation Distance (TVD)
    TVD_nodd = 0.5 * np.sum(np.abs(P_ideal - P_nodd))
    TVD_dd = 0.5 * np.sum(np.abs(P_ideal - P_dd))

    # Target State Populations
    POP_ideal = sum(ideal_counts.get(s, 0) for s in target_states) / N_SHOTS_IDEAL
    POP_nodd = sum(counts_no_em.get(s, 0) for s in target_states) / N_SHOTS_NO_EM
    POP_dd = sum(counts_em.get(s, 0) for s in target_states) / N_SHOTS_EM

    # Relative improvements
    TVD_reduction = (TVD_nodd - TVD_dd) / TVD_nodd * 100 if TVD_nodd > 1e-9 else 0.0
    POP_increase = (POP_dd - POP_nodd) / POP_nodd * 100 if POP_nodd > 1e-9 else 0.0

    return {
        "N_QUBITS": num_qubits,
        "N_SHOTS_NODD": N_SHOTS_NO_EM,
        "N_SHOTS_DD": N_SHOTS_EM,
        "N_SHOTS_IDEAL": N_SHOTS_IDEAL,
        "TVD_nodd": TVD_nodd,
        "TVD_dd": TVD_dd,
        "TVD_reduction_percent": TVD_reduction,
        "POP_ideal": POP_ideal,
        "POP_nodd": POP_nodd,
        "POP_dd": POP_dd,
        "POP_increase_percent": POP_increase,
    }


def cal_em_eff_estimator(
    evs_no_em: float, evs_em: float, evs_ideal: float
) -> Dict[str, Union[float, str]]:
    """
    Evaluates error mitigation efficacy based on Expected Value (EVS) results
    received from the Estimator primitive.

    Args:
        evs_no_em (float): Observed EVS without error mitigation.
        evs_em (float): Observed EVS with error mitigation.
        evs_ideal (float): Theoretical (ideal) EVS value. Assumed to be zero.

    Returns:
        Dict[str, Union[float, str]]: Error values and percentage reduction due to mitigation.
    """
    deviation_no_em = abs(evs_no_em - evs_ideal)
    deviation_em = abs(evs_em - evs_ideal)

    deviation_reduction = (
        (deviation_no_em - deviation_em) / deviation_no_em * 100
        if deviation_no_em > 1e-9
        else 0.0
    )

    return {
        "EVS_ideal": evs_ideal,
        "EVS_nodd": evs_no_em,
        "EVS_dd": evs_em,
        "ERROR_nodd": deviation_no_em,
        "ERROR_dd": deviation_em,
        "ERROR_reduction_percent": deviation_reduction,
    }
