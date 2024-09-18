import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse.linalg import spsolve
from scipy.sparse import csc_matrix

from parameters import *
from ode_solver import ode_solver

def thermal_hydraulics(y_th, q_prime, Ts_core_0, params, step):
    Vc = params['Vc']
    U = params['U']
    Ms = params['Ms']
    Mg = params['Mg']
    c_p_s = params['c_p_s']
    c_p_g = params['c_p_g']
    L = params['L']
    gamma = params['gamma']
    N = params['N']
    dz = params['dz']
    bc_s0 = params['bc_s0']
    bc_sL = params['bc_sL']
    bc_g0 = params['bc_g0']
    bc_gL = params['bc_gL']
    initialS = params['initialS']
    initialG = params['initialG']
    err=params['err']
    
    # parameters transformation
    a_th = Vc
    b_th = U / (Ms * c_p_s)
    d_th = L * gamma / (Ms * c_p_s)
    c_th = U / (Mg * c_p_g)
    e_th = L * (1 - gamma) / (Mg * c_p_g)

    # discretize the spatial domain
    # AT=np.diag(-np.ones(N-1), -1)+ np.diag(np.ones(N-1), 1)
    # AT[0, 0] = AT[-1, -1] = 0
    # AT=AT / 2*dz
    # # AT=np.diag(-np.ones(N))+ np.diag(np.ones(N-1), 1)+ np.diag(np.ones(N-1), -1)
    # AT[0, :] = 0
    # AT[-1,:] = 0
    # AT[0, 0] = 1
    # AT[-1, -1] = 1
    # AT=AT/dz
    # print(AT)
    # AT_sparse = csc_matrix(AT)
    AT = np.diag(-2 * np.ones(N)) + np.diag(np.ones(N-1), 1) + np.diag(np.ones(N-1), -1)
    AT[0, 0] = AT[-1, -1] = 1
    AT[0, 1] = AT[-1, -2] = 0
    AT=AT / dz**2
    AT_sparse = csc_matrix(AT)
    # print("Test th")

    # print(y_th.shape)
    y_th[0] = Ts_core_0
    
    def pde_to_ode_th(t, y):
        # print("testThermal")
        temperature_fuel = y[:N]
        temperature_graphite = y[N:]
        temperature_fuel_dt = a_th * (AT_sparse @ temperature_fuel) + b_th * (temperature_graphite-temperature_fuel)+d_th*q_prime.T + err
        temperature_graphite_dt = c_th * (temperature_fuel-temperature_graphite) + e_th * q_prime.T + err
        # print(f'd_th: {d_th * q_prime.T}')
        # print(f'e_th: {e_th * q_prime.T}')
        # Apply time-varying boundary conditions
        temperature_fuel_dt[0] = bc_s0 - temperature_fuel[0]
        temperature_fuel_dt[-1] = bc_sL - temperature_fuel[-1]
        temperature_graphite_dt[0] = bc_g0 - temperature_graphite[0]
        temperature_graphite_dt[-1] = bc_gL - temperature_graphite[-1]
        # Combine the derivatives
        dydt = np.concatenate([temperature_fuel_dt, temperature_graphite_dt])
        # print(y.shape)
        # print(temperature_fuel.shape)
        # print(temperature_graphite.shape)
        return dydt
    
    # Initial condition vector
    if step==0:
        # print("test3")
        y0 = np.concatenate([initialS, initialG])
    else:
        y0 = y_th[:,-1]
    # print("y0shape: "+str(y0.shape))
    
    bc=[]
    solution_y_th = ode_solver(y0, bc, pde_to_ode_th, params)
    
    y_th = solution_y_th.y
    
    # print(y_th.shape)

    return y_th