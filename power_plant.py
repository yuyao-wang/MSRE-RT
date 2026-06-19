import numpy as np


def power_plant_temp(T_heater_outlet, params, step):
    gamma_b = params["brayton_gamma"]
    eta_c = params["brayton_eta_c"]
    eta_t = params["brayton_eta_t"]
    pi_c = params["brayton_pi_c"]
    pi_t = params["brayton_pi_t"]
    epsilon_rec = params["brayton_recuperator_efficiency"]
    T1 = params["brayton_cooler_outlet_temp"]
    T3 = max(float(T_heater_outlet), T1 + 5.0)

    T2s = T1 * pi_c ** ((gamma_b - 1.0) / gamma_b)
    T2 = T1 + (T2s - T1) / eta_c

    T4s = T3 * pi_t ** (-(gamma_b - 1.0) / gamma_b)
    T4 = T3 - eta_t * (T3 - T4s)

    requested_recuperation = epsilon_rec * max(T4 - T2, 0.0)
    approach_limit = max(T3 - params["brayton_min_heater_approach"] - T2, 0.0)
    delta_recuperation = min(requested_recuperation, approach_limit)

    T2r = T2 + delta_recuperation
    T4r = T4 - delta_recuperation

    design_mass_flow = float(params["brayton_mdot"])
    cp_b = params["c_p_sss"]
    heater_duty_per_kg = cp_b * max(T3 - T2r, 0.0)
    available_heat = float(params.get("brayton_available_heat_W", np.inf))
    if heater_duty_per_kg > 0.0 and np.isfinite(available_heat):
        mass_flow = min(design_mass_flow, available_heat / heater_duty_per_kg)
    else:
        mass_flow = design_mass_flow

    W_c = mass_flow * cp_b * max(T2 - T1, 0.0)
    W_t = mass_flow * cp_b * max(T3 - T4, 0.0)
    W_net = W_t - W_c
    Q_in = mass_flow * heater_duty_per_kg
    Q_out = mass_flow * cp_b * max(T4r - T1, 0.0)

    params["last_power_plant"] = {
        "step": step,
        "T1": T1,
        "T2": T2,
        "T2r": T2r,
        "T3": T3,
        "T4": T4,
        "T4r": T4r,
        "W_c": W_c,
        "W_t": W_t,
        "W_net": W_net,
        "Q_in": Q_in,
        "Q_out": Q_out,
        "available_heat": available_heat,
        "mass_flow_effective": mass_flow,
        "model": "ideal_gas_surrogate",
        "eta_b": W_net / max(Q_in, 1.0e-12),
    }

    return T2r
