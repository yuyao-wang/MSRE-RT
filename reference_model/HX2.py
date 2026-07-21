from heat_exchanger import solve_heat_exchanger

def HX2(y_hx2, Ts_HX2_L, Tss_HX2_0, params, step):
    # The exchanger input is a lumped overall conductance (UA), so the
    # distributed coefficient is formed as UA / (M c_p).
    ua_hx2 = params.get("UA2_hx", params["U2_hx"])
    config = {
        "dx": params["L_HX2"] / max(params["Nx"] - 1, 1),
        "hot_velocity": -params["V_he2_s"],
        "cold_velocity": params["V_he2_ss"],
        "hot_exchange_coeff": ua_hx2 / (params["M_he2_s"] * params["c_p_ss"]),
        "cold_exchange_coeff": ua_hx2 / (params["M_he2_ss"] * params["c_p_sss"]),
        "hot_initial": params["u2_init"],
        "cold_initial": params["v2_init"],
    }

    return solve_heat_exchanger(y_hx2, Ts_HX2_L, Tss_HX2_0, config, params, step)
