from collections import deque

import numpy as np


def initialize_precursor_loop_state(
    precursor_groups,
    seed_outlet,
    outer_dt,
    tau_loop,
):
    seed_outlet = np.asarray(seed_outlet, dtype=float)
    history_size = max(3, int(np.ceil(max(tau_loop, outer_dt) / outer_dt)) + 3)
    times = deque(maxlen=history_size)
    outlets = deque(maxlen=history_size)

    for idx in range(history_size):
        times.append((idx - history_size + 1) * outer_dt)
        outlets.append(seed_outlet.copy())

    return {
        "times": times,
        "outlets": outlets,
        "last_outlet": seed_outlet.copy(),
    }


def _interpolate_outlet(loop_state, target_time):
    times = np.asarray(loop_state["times"], dtype=float)
    outlets = np.asarray(loop_state["outlets"], dtype=float)

    if target_time <= times[0]:
        return outlets[0].copy()
    if target_time >= times[-1]:
        return outlets[-1].copy()

    idx = int(np.searchsorted(times, target_time))
    t0 = times[idx - 1]
    t1 = times[idx]
    if t1 == t0:
        return outlets[idx].copy()

    weight = (target_time - t0) / (t1 - t0)
    return (1.0 - weight) * outlets[idx - 1] + weight * outlets[idx]


def precursor_inlet_from_loop(params, current_time):
    precursor_groups = int(params["precursor_groups"])
    mode = params.get("inlet_mode", "recirculate")

    if mode == "fresh":
        return np.zeros(precursor_groups, dtype=float)

    loop_state = params["precursor_loop_state"]
    if mode == "copy":
        return np.asarray(loop_state["last_outlet"], dtype=float).copy()

    tau_loop = float(params["precursor_loop_tau"])
    eta_loop = float(params["precursor_loop_efficiency"])
    lambda_i = np.asarray(params["lambda_i_np"], dtype=float)

    delayed_outlet = _interpolate_outlet(loop_state, current_time - tau_loop)
    return eta_loop * delayed_outlet * np.exp(-lambda_i * tau_loop)


def record_precursor_outlet(params, time, outlet):
    loop_state = params["precursor_loop_state"]
    outlet = np.asarray(outlet, dtype=float)
    loop_state["times"].append(float(time))
    loop_state["outlets"].append(outlet.copy())
    loop_state["last_outlet"] = outlet.copy()
