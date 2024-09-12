import numpy as np

def generate_parameters(
    # Neutronics
    dt=0.1, # fixed time step, 0.5
    L = 172,  # Length of the spatial domain, cm
    # L = 22.9
    N = 200,  # Number of spatial points
    A = 4094,  # Area of the reactor, cm^2
    flux_to_power = 3.12e10,    # 3.12e10, fissions/watt-sec
    # volume = 18 * 1e3, # volume of reactor
    # V = 4e5
    V = 1.103497 * 1e7,  # cm/s   
    # V = 2.2e5,        
    # D = 0.390016 * 8   
    D = 0.96343 * 7,  # cm 
    # D = 1.02,  
    # sigma_a =0.0835   
    sigma_a = 0.00217, # 0.0021701, 1701-e, 1702-0, cm^-1, 0.002161939172413793, 7.33-explode, 7.325-converge to 0     
    nu_sigma_f = 0.00442, # 0.00442, 0.00442-e, cm^-1, 0.004411764705882353, 3.33029e-2, 6.9- explode at 7.33, 6.9-converge to 0 at 7.325
    # sigma_a = 0.00054869,
    # nu_sigma_f = 0.00098328,
    # nu_sigma_f = 3.33029
    sigma_f = 0.00442/2,  
    beta = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088], # Delayed neutron fractions
    # Beta = sum(beta),      # 0.00264
    # Beta = 0.0045
    # delta=Beta*nu_sigma_f
    # beta2 = [0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088]
    lambda_i = [0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5],    # Decay constants
    # lambda_i = [0.08, 0.08, 0.08, 0.08, 0.08, 0.08]    # Decay constants
    # sum(lambda_i) = 4.1403        # 0.08
    # initial condition
    # phi_0= 5226.54 * np.ones(N); #5226.54
    # c0 = (delta / (sum(lambda_i)/6)) * phi_0

    # Thermal-Hydraulics
    c_p_s = 2090,  # 1983, Specific heat of primary salt, J/kgK
    c_p_g = 1757,    # 1757, Specific heat of graphite, J/kg K
    Vc = 0.2,    # Salt velocity in the core, m/s
    # Vc = 20,
    Ms = 1448,   # 1448, Fuel salt mass in the core, kg
    Mg = 3687,   # 3687, Mass of graphite in the core, kg
    gamma = 0.93,    # 0.93, Fraction of power released in the salt
    U = 36000,   # Overall heat transfer coefficient between salt and graphite, W/K
    # U = 1800,
    # Temp input for test:
    # Amplitude = 4.5e6;
    # q_prime=Amplitude * sin(pi * linspace(0, L, N) / L)';
    # q_prime=Amplitude;
    # Boundary conditions
    # bc_s0 = 910,
    # bc_sL = 958.15,
    # bc_g0 = 920,
    # bc_gL = 968.71,
    # s_ref = 
    # bc_s0 = 922,
    # bc_sL = 935,
    # bc_g0 = 922,
    # bc_gL = 1100,
    # bc_s0 = 700,
    # bc_sL = 800,
    # bc_g0 = 700,
    # bc_gL = 1000,
    bc_s0 = 300,
    bc_sL = 500,
    bc_g0 = 300,
    bc_gL = 500,
    # Initial conditions
    # initialS = (bc_s0 + (bc_sL - bc_s0) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L, N) ) / (L*2))) * 0.8).T
    # initialG = (bc_g0 + (bc_gL - bc_g0) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L, N) ) / (L*2))) * 1.05).T
    # referenceS=930
    # referenceG=931.15
    # Heat Exchanger 1
    err = 0,
    # Nx = N  # Number of spatial points
    L_HX = 2,    # length of the spatial domain
    # dx = L / (N - 1)    # Spatial step size
    # V_s0 = Vc   # Salt velocity in the core m/s
    V_he_s = 75.7 * 1e-3 / 23.6, #0.003207627118644068 m/s
    V_he_ss = 53.6 * 1e-3 / 23.6,    # 0.002271186440677966 m/s
    U_hx = 82800,    # Heat transfer coefficient between primary and secondary salt, W/K
    M_he_s = 342,    # Mass of salt in the heat exchanger (fuel side), kg
    M_he_ss = 117,   # Mass of salt in the heat exchanger (coolant side), kg
    c_p_ss = 2416,   # Specific heat of secondary salt, J/kg/K
    # Initial conditions
    # u_L = 900.15,
    # u_H = 958,
    # v_L = 824.85,
    # v_H = 866.45,
    u_L = 800,
    u_H = 850,
    v_L = 824.85,
    v_H = 866.45,
    # u_L = 0,
    # u_H = 0,
    # v_L = 0,
    # v_H = 0,
    # initial conditions using a sine function
    # u_init = u_L + (u_H - u_L) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L_HX, Nx) / L_HX))).T
    # v_init = v_L + (v_H - v_L) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L_HX, Nx) / L_HX))* 1.05).T

    # Heat Exchanger 2, TODO: change the parameters
    L_HX2 = 2,    # length of the spatial domain
    V_he2_s = 53.6 * 1e-3 / 23.6, #0.003207627118644068 m/s
    V_he2_ss = 33.6 * 1e-3 / 23.6,    # 0.002271186440677966 m/s
    U2_hx = 82800,    # Heat transfer coefficient between primary and secondary salt, W/K
    M_he2_s = 117,    # Mass of salt in the heat exchanger (fuel side), kg
    M_he2_ss = 100,   # Mass of salt in the heat exchanger (coolant side), kg
    c_p_sss = 2416,   # Specific heat of secondary salt, J/kg/K
    # Initial conditions
    u2_L = 824,
    u2_H = 866,
    v2_L = 744,
    v2_H = 786,
    # initial conditions using a sine function
    # u2_init = u2_L + (u2_H - u2_L) * (0.5 + 0.7 * np.sin(np.pi * (np.linspace(0, L_HX2, Nx) / L_HX2))).T
    # v2_init = v2_L + (v2_H - v2_L) * (0.5 + 0.7 * np.sin(np.pi * (np.linspace(0, L_HX2, Nx) / L_HX2))* 1.05).T

    # Reactivity
    # rho_init = 0 * np.ones(N)
    alpha_f    = 5.904E-5,  # -5.904E-5, U233 (drho/K) fuel salt temperature-reactivity feedback coefficient ORNL-TM-1647 p.3 % -5.904E-05; % ORNL-TM-0728 p. 101 %
    alpha_g    = 6.624E-5,  # -6.624E-5, U233  (drho/K) graphite temperature-reactivity feedback coefficient ORNL-TM-1647 p.3 % -6.624E-05; % ORNL-TM-0728 p.101
    tau_l  = 16.44,  # ORNL-TM-0728 %16.44; % (s)
    tau_c  = 8.460,   # ORNL-TM-0728 %8.460; % (s)

    # Transport Delays
    # Pure time delays between components
    tau_hx_c = 1, # (sec) delay from hx to core TDAMSRE p.6
    tau_c_hx = 1, # (sec) subtracted 1 sec for external loop power generation node resident time; delay from core to fuel hx TDAMSRE p.6
    tau_hx_r = 1, # (sec) fertile hx to core TDAMSRE p.6
    tau_r_hx = 1, # (sec) core to fertile hx TDAMSRE p.6
    tau_r_pp = 1, # TODO:delay from HX2 to the power plant, to be fixed
    tau_pp_r = 1, # TODO:delay from the power plant to HX2, to be fixed
    scale = 1,
    rho_init = 0,
    ):
    
    dz = L / (N - 1)  # Spatial step size, m
    Nx = N
    dx = L / (Nx - 1)
    Beta = sum(beta)
    delta=Beta*nu_sigma_f
    phi_0 = 1e13 * np.ones(N)  # 3.111, 15.778, 20, 5226.54, Initial neutron flux, n/cm^2/s
    # c0 = (sum(beta) * nu_sigma_f) / (sum(lambda_i)/6) * phi_0  # Initial precursor concentration
    c0 = np.zeros(6 * N)
    for i in range(6):
        c0[i * N:(i + 1) * N] = (np.mean(beta) * nu_sigma_f) / (np.mean(lambda_i)) * phi_0
       
    initialS = (bc_s0 + (bc_sL - bc_s0) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L, N) ) / (L*2))) * 0.8).T
    initialG = (bc_g0 + (bc_gL - bc_g0) * (0.5 + 0.5 * np.sin(np.pi * (np.linspace(0, L, N) ) / (L*2))) * 1.05).T
    # Initial conditions for heat exchangers
    u_init = bc_s0 + (bc_sL - bc_s0) * (0.5 + 0.5 * np.sin(np.pi * np.linspace(0, L_HX2, N) / L_HX2))
    v_init = bc_g0 + (bc_gL - bc_g0) * (0.5 + 0.5 * np.sin(np.pi * np.linspace(0, L_HX2, N) / L_HX2) * 1.05)
    u2_init = bc_s0 + (bc_sL - bc_s0) * (0.5 + 0.7 * np.sin(np.pi * np.linspace(0, L_HX2, N) / L_HX2))
    v2_init = bc_g0 + (bc_gL - bc_g0) * (0.5 + 0.7 * np.sin(np.pi * np.linspace(0, L_HX2, N) / L_HX2) * 1.05)
    # Initial conditions - DONE
    Ts_in=bc_s0
    Ts_out=bc_sL
    Tss_in=v_L
    Tss_out=v_H
    Tsss_in=v2_L
    Tsss_out=v2_H
    
    return {
        'dt': dt,
        'L': L,
        # 'volume': volume,
        'N': N,
        'dz': dz,
        'flux_to_power': flux_to_power,
        'A': A,
        'V': V,
        'D': D,
        'sigma_a': sigma_a,
        'nu_sigma_f': nu_sigma_f,
        'sigma_f': sigma_f,
        'beta': beta,
        'lambda_i': lambda_i,
        'phi_0': phi_0,
        'c0': c0,
        'c_p_s': c_p_s,
        'Vc': Vc,
        'Ms': Ms,
        'Mg': Mg,
        'gamma': gamma,
        'U': U,
        'c_p_g': c_p_g,
        'bc_s0': bc_s0,
        'bc_sL': bc_sL,
        'bc_g0': bc_g0,
        'bc_gL': bc_gL,
        'V_he_s': V_he_s,
        'V_he_ss': V_he_ss,
        'U_hx': U_hx,
        'M_he_s': M_he_s,
        'M_he_ss': M_he_ss,
        'c_p_ss': c_p_ss,
        'L_HX2': L_HX2,
        'V_he2_s': V_he2_s,
        'V_he2_ss': V_he2_ss,
        'U2_hx': U2_hx,
        'M_he2_s': M_he2_s,
        'M_he2_ss': M_he2_ss,
        'c_p_sss': c_p_sss,
        'rho_init': rho_init,
        'alpha_f': alpha_f,
        'alpha_g': alpha_g,
        'tau_l': tau_l,
        'tau_c': tau_c,
        'tau_hx_c': tau_hx_c,
        'tau_c_hx': tau_c_hx,
        'tau_hx_r': tau_hx_r,
        'tau_r_hx': tau_r_hx,
        'tau_r_pp': tau_r_pp,
        'tau_pp_r': tau_pp_r,
        'u_init': u_init,
        'v_init': v_init,
        'u2_init': u2_init,
        'v2_init': v2_init,
        'err': err,
        'Nx': Nx,
        'dx': dx,
        'u_L': u_L,
        'u_H': u_H,
        'v_L': v_L,
        'v_H': v_H,
        'u2_L': u2_L,
        'u2_H': u2_H,
        'v2_L': v2_L,
        'v2_H': v2_H,
        'Ts_in': Ts_in,
        'Ts_out': Ts_out,
        'Tss_in': Tss_in,
        'Tss_out': Tss_out,
        'Tsss_in': Tsss_in,
        'Tsss_out': Tsss_out,
        'initialS': initialS,
        'initialG': initialG,
        'scale': scale  
    }

# Generate default parameters
parameters = generate_parameters()
