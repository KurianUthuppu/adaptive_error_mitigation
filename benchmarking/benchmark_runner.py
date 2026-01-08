import sys
sys.path.append(r"C:\Users\shrey")

import numpy as np
import pandas as pd
import json
from sklearn.linear_model import LogisticRegression

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit_aer.primitives import EstimatorV2 as AEREstimator
from qiskit_ibm_runtime import QiskitRuntimeService, Estimator, EstimatorOptions

from adaptive_error_mitigation.analytics import (
    extract_backend_metrics,
    analyze_qubit_idling,
)
from adaptive_error_mitigation.utils import cal_em_eff_estimator
from adaptive_error_mitigation.benchmarking import dd_benchmark_circuit, zne_benchmark_circuit
from adaptive_error_mitigation.mitigation.strategies import calculate_h_zne

service = QiskitRuntimeService(name = 'Reserach_IITJ')
Backend_list = service.backends()
threshold_file = r"config.json"

def load_json(file_name):
    with open(file_name, "r") as f:
        thresholds = json.load(f)
    return thresholds

def update_json(thresholds, file_name):
    with open(file_name, "w") as f:
        json.dump(thresholds, f, indent=4)

# Dynamical Decoupling
def dd_benchmarking(thresholds):
    QUBITS = [7, 8, 10, 11, 13, 16, 19, 22, 25, 28, 31, 34, 37, 38, 40, 41, 43, 46, 49, 50, 52, 55]
    estimator_options = EstimatorOptions(
        dynamical_decoupling={"enable": False},
        twirling={"enable_gates": False, "enable_measure": False},
        resilience_level=0,
        max_execution_time=50,
    )
        
    for backend in Backend_list:
        df = pd.DataFrame(columns=["num_qubits", "max_decoher_err_prob", "evs_ideal", "evs_nodd", "evs_dd", "error_nodd", "error_dd", "error_improvement_percent"])
        estimator = Estimator(mode=backend, options=estimator_options)

        for num_qubit in QUBITS:
            isa_qc, dd_circ_measured, isa_observable = dd_benchmark_circuit(num_qubit, backend)
            
            idling_analysis = analyze_qubit_idling(isa_qc, backend)
            max_decoher_err_prob = idling_analysis["max_ratio_qubit"]["decoher_err_prob"]

            aerEstimator = AEREstimator()
            evs_ideal = aerEstimator.run([(dd_circ_measured, isa_observable)]).result()[0].data.evs
            
            result = estimator.run([(isa_qc, isa_observable), (dd_circ_measured, isa_observable)]).result()
            evs_nodd = result[0].data.evs
            evs_dd_xx = result[1].data.evs

            results = cal_em_eff_estimator(evs_nodd, evs_dd_xx, evs_ideal)

            row = pd.DataFrame({
                "num_qubits" : [num_qubit],
                "max_decoher_err_prob" : [max_decoher_err_prob],
                "evs_ideal" : [evs_ideal],
                "evs_nodd" : [results['EVS_nodd']],
                "evs_dd" : [results['EVS_dd']],
                "error_nodd" : [results['ERROR_nodd']],
                "error_dd" : [results['ERROR_dd']],
                "error_improvement_percent" : [results["ERROR_reduction_percent"]]
            })
            df = pd.concat([df, row], ignore_index=True)

        X = df[["max_decoher_err_prob"]].values  # shape (n_samples, 1)
        y = (df["error_improvement_percent"] > 0).astype(int)  # shape (n_samples,)
        clf = LogisticRegression().fit(X, y)
        p = np.linspace(X.min(), X.max(), 200).reshape(-1,1)
        probs = clf.predict_proba(p)[:,1]
        threshold_ml = p[np.argmin(np.abs(probs - 0.5))][0]
        
        if backend.name not in thresholds:
            thresholds[backend.name] = {}
        thresholds[backend.name]["DD_ERROR_THRESHOLD"] = float(threshold_ml)

    print("Thresholds for Dynamical Decoupling Updated!!!")

# Zero Noise Extraplation
def zne_benchmarking(thresholds):
    # QUBITS = [7, 8, 10, 11, 13, 16, 19, 22, 25, 28, 31, 34, 37, 38, 40, 41, 43, 46, 49, 50, 52, 55]
    QUBITS = [5, 10, 15, 20]
    estimator_options_nozne = EstimatorOptions(
        dynamical_decoupling={"enable": False},
        twirling={"enable_gates": False, "enable_measure": False},
        resilience_level= 0,
        resilience = {
            "zne_mitigation": False,
            "zne" : {
                "noise_factors": (1, 3, 5),
                "extrapolator": "exponential",
            },
        },
    )
    estimator_options_zne = EstimatorOptions(
        dynamical_decoupling={"enable": False},
        twirling={"enable_gates": False, "enable_measure": False},
        resilience_level= 2,
        resilience = {
            "zne_mitigation": True,
            "zne" : {
                "amplifier": "gate_folding",
                "noise_factors": (1, 3, 5),
                "extrapolator": "exponential",
            },
        },
    )

    for backend in Backend_list:
        df = pd.DataFrame(columns=["num_qubits", "h_zne", "evs_ideal", "evs_nozne", "evs_zne", "error_nozne", "error_zne", "error_improvement_percent"])
        estimator_no_zne = Estimator(mode=backend, options=estimator_options_nozne)
        estimator_zne = Estimator(mode=backend, options=estimator_options_zne)

        for num_qubit in QUBITS:
            isa_qc, isa_observable = zne_benchmark_circuit(num_qubit, backend)

            metrics = calculate_h_zne(isa_qc, backend)
            h_zne = metrics["h_zne"]

            aerEstimator = AEREstimator()
            evs_ideal = aerEstimator.run([(isa_qc, isa_observable)]).result()[0].data.evs
            
            evs_nozne = estimator_no_zne.run([(isa_qc, isa_observable)]).result()[0].data.evs
            evs_zne = estimator_zne.run([(isa_qc, isa_observable)]).result()[0].data.evs

            results = cal_em_eff_estimator(evs_nozne, evs_zne, evs_ideal)

            row = pd.DataFrame({
                "num_qubits" : [num_qubit],
                "h_zne" : [h_zne],
                "evs_ideal" : [evs_ideal],
                "evs_nozne" : [results['EVS_nodd']],
                "evs_zne" : [results['EVS_dd']],
                "error_nozne" : [results['ERROR_nodd']],
                "error_zne" : [results['ERROR_dd']],
                "error_improvement_percent" : [results["ERROR_reduction_percent"]]
            })
            df = pd.concat([df, row], ignore_index=True)

        X = df[["h_zne"]].values  # shape (n_samples, 1)
        y = (df["error_improvement_percent"] > 0).astype(int)  # shape (n_samples,)
        clf = LogisticRegression().fit(X, y)
        p = np.linspace(X.min(), X.max(), 200).reshape(-1,1)
        probs = clf.predict_proba(p)[:,1]

        # Find all h_zne where prob > 0.5
        mask = probs > 0.5
        zne_min = float(p[mask].min())
        zne_max = float(p[mask].max())

        # Store thresholds
        if backend.name not in thresholds:
            thresholds[backend.name] = {}

        thresholds[backend.name]["ZNE_MIN_THRESHOLD"] = zne_min
        thresholds[backend.name]["ZNE_MAX_THRESHOLD"] = zne_max
        thresholds[backend.name]["ZNE_NOISE_FACTORS"] = list((1, 3, 5))
        thresholds[backend.name]["ZNE_EXTRAPOLATOR"] = "exponential"
        thresholds[backend.name]["ZNE_AMPLIFIER"] = "gate_folding"

    print("Thresholds for ZNE Updated!!!")

if __name__ == "__main__":
    thresholds = load_json(threshold_file)
    # dd_benchmarking(thresholds)
    zne_benchmarking(thresholds)
    update_json(thresholds, threshold_file)