from heat_exchanger import solve_heat_exchanger

def HX1(y_hx1, Ts_HX1_L, Tss_HX1_0, params, step):
    config = {
        "dx": params["L_HX"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he_s"],
        "cold_velocity": params["V_he_ss"],
        "hot_exchange_coeff": params["U_hx"] / (params["M_he_s"] * params["c_p_s"]),
        "cold_exchange_coeff": params["U_hx"] / (params["M_he_ss"] * params["c_p_ss"]),
        "hot_initial": params["u_init"],
        "cold_initial": params["v_init"],
    }

    return solve_heat_exchanger(y_hx1, Ts_HX1_L, Tss_HX1_0, config, params, step)
