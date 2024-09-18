from scipy.sparse.linalg import spsolve
import numpy as np
from numpy.linalg import inv
from scipy.sparse import csc_matrix

from ode_solver import ode_solver

def neutronics(y_n, rho, step, params):
    # Extract relevant parameters from the params dictionary
    N = params['N']
    dt = params['dt']
    dz = params['dz']
    V = params['V']
    D = params['D']
    sigma_a = params['sigma_a']
    nu_sigma_f = params['nu_sigma_f']
    Beta = sum(params['beta'])
    beta = params['beta']
    lambda_i = params['lambda_i']

    # Discretize the spatial domain and set up the Crank-Nicolson matrices
    main_diag = -2 * np.ones(N)
    off_diag = np.ones(N - 1)
    D2 = (np.diag(main_diag) + np.diag(off_diag, 1) + np.diag(off_diag, -1)) / dz**2
    
    # Boundary conditions: Dirichlet boundary conditions for zero flux at boundaries
    D2[0, :] = 0
    D2[-1, :] = 0
    D2[0, 0] = 1
    D2[-1, -1] = 1
    
    D2_sparse = csc_matrix(D2)
    I = np.eye(N)
    A = csc_matrix(I - 0.5 * dt * V * D * D2_sparse)
    B = csc_matrix(I + 0.5 * dt * V * D * D2_sparse)
    # B = V * D * dt * D2
    # Compute Keff (effective multiplication factor)
    Keff = 1 / (np.ones(N) - rho)
    print(f"Keff(N/2): {Keff[int(N/2)]}, Keff(0): {Keff[0]}, Keff(N-1): {Keff[N-1]}, Keff(avg): {Keff.mean()}")  

    def pde_to_ode_neutronics(t, y):
        phi = y[:N]

        # Apply Crank-Nicolson method
        lambda_ci = np.zeros(N)
        for i in range(6):
            lambda_ci += lambda_i[i] * y[(i + 1) * N:(i + 2) * N]

        rhs_phi = B @ phi + dt * V * ((-sigma_a + ((1 - Beta) * (1 + rho) * nu_sigma_f)) * phi + lambda_ci)

        phi_new = spsolve(A, rhs_phi)
        dphi_dt = (phi_new - phi) / dt
        # dphi_dt = rhs_phi / dt

        dci_dt = np.zeros((6, N))
        for i in range(6):
            dci_dt[i] = beta[i] * (nu_sigma_f) * phi - (lambda_i[i] * y[(i + 1) * N:(i + 2) * N])
        
        return np.concatenate([dphi_dt, dci_dt[0], dci_dt[1], dci_dt[2], dci_dt[3], dci_dt[4], dci_dt[5]])

    # Initial condition vector
    if step == 0:
        phi_0 = params['phi_0']
        c0 = params['c0']
        y0 = np.concatenate([phi_0, c0[:N], c0[N:2*N], c0[2*N:3*N], c0[3*N:4*N], c0[4*N:5*N], c0[5*N:]])
    else:
        y0 = y_n

    # Solve the system of ODEs
    bc = []
    solution_y_n = ode_solver(y0, bc, pde_to_ode_neutronics, params)

    # Extract the solution
    phi = solution_y_n.y[:N, -1].T
    q_prime = phi
    y_n = solution_y_n.y

    return y_n, q_prime
