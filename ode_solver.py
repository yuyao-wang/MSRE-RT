# from scipy.integrate import solve_ivp
import numpy as np

from ivp import solve_ivp

from parameters import *
# TODO: ic, bc, vector to be solved (by pde_to_ode function), ode solving time span, solving method

def ode_solver(ic, bc, vector_to_be_solved, params):
    # Initial condition vector
    y0 = ic
    # Boundary condition vector
    bc = bc
    
    dt=params['dt']
    t = np.linspace(0, 1, int(1/dt))   # Time vector
    
    time_span=(0,1)
    # Solve the system of ODEs
    solution = solve_ivp(vector_to_be_solved, time_span, y0, method='RK23')
    
    return solution