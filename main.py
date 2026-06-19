import numpy as np
import os
from collections import deque

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - optional plotting dependency
    plt = None

from parameters import generate_parameters
from neutronics import neutronics
from thermal_hydraulics import thermal_hydraulics
from HX1 import HX1
from HX2 import HX2
from transport_delay import transport_delay
from power_plant import power_plant_temp


def external_reactivity_from_schedule(params, time_s):
    schedule = params.get('reactivity_schedule_pcm', [(0.0, 0.0)])
    current_pcm = float(schedule[0][1])
    for event_time, value_pcm in schedule:
        if float(time_s) >= float(event_time):
            current_pcm = float(value_pcm)
        else:
            break
    return current_pcm * 1.0e-5


def save_ci_groups_csv(selected_step, ci_groups_at_step, params, index):
    os.makedirs('simulation_results', exist_ok=True)

    dt = params.get('dt', 1.0)
    time_value = selected_step * dt
    n_points = ci_groups_at_step.shape[1]
    z = np.linspace(0.0, params['L'], n_points)

    csv_path = f'simulation_results/ci_groups_step_{selected_step}_sim_{index}.csv'
    header = 'simulation_index,step,time,point_index,z,C1,C2,C3,C4,C5,C6'

    rows = np.zeros((n_points, 11), dtype=float)
    rows[:, 0] = index
    rows[:, 1] = selected_step
    rows[:, 2] = time_value
    rows[:, 3] = np.arange(n_points)
    rows[:, 4] = z
    rows[:, 5:] = ci_groups_at_step.T

    np.savetxt(csv_path, rows, delimiter=',', header=header, comments='')
    print(f"Saved Ci groups at step {selected_step} to {csv_path}")
    
def run_simulation(params, index):
    time_span = int(params.get('time_span', 600))
    selected_step = min(int(params.get('selected_step', time_span - 1)), time_span - 1)
    N = params['N']
    Nx = params['Nx']
    mid_idx = N // 2
    precursor_groups = params['precursor_groups']
    verbose = params.get('verbose', False)
    log_every = params.get('log_every', 1)
    initialS = params['initialS']
    initialG = params['initialG']

    # Extract parameters
    rho = np.zeros(N)
    rod_position = 0.0
    y_n_seed = np.asarray(params.get('y_n_init', []), dtype=float)
    if y_n_seed.size == params['neutronics_state_size']:
        y_n = y_n_seed.reshape(-1, 1)
    else:
        y_n = np.zeros((params['neutronics_state_size'], 1))
    q_prime = np.zeros(N)
    y_th_seed = np.asarray(params.get('y_th_init', []), dtype=float)
    y_hx1_seed = np.asarray(params.get('y_hx1_init', []), dtype=float)
    y_hx2_seed = np.asarray(params.get('y_hx2_init', []), dtype=float)
    y_th = np.zeros((2 * N, 1))
    y_hx1 = np.zeros((2 * Nx, 1))
    y_hx2 = np.zeros((2 * Nx, 1))
    if y_th_seed.size == 2 * N:
        y_th[:, 0] = y_th_seed.reshape(-1)
    if y_hx1_seed.size == 2 * Nx:
        y_hx1[:, 0] = y_hx1_seed.reshape(-1)
    else:
        y_hx1[:, 0] = np.concatenate([params['u_init'], params['v_init']])
    if y_hx2_seed.size == 2 * Nx:
        y_hx2[:, 0] = y_hx2_seed.reshape(-1)
    else:
        y_hx2[:, 0] = np.concatenate([params['u2_init'], params['v2_init']])
    
    Tss_HX2_0 = params['Tss_in']
    Ts_HX1_0 = params['Ts_in']
    Tss_HX1_0 = params['Tss_in']
    Tsss_pp_0 = params['Tsss_in']
    buffer_hx_c = deque(params.get('buffer_hx_c_init', []))
    buffer_c_hx = deque(params.get('buffer_c_hx_init', []))
    buffer_r_hx = deque(params.get('buffer_r_hx_init', []))
    buffer_hx_r = deque(params.get('buffer_hx_r_init', []))
    buffer_r_pp = deque(params.get('buffer_r_pp_init', []))
    buffer_pp_r = deque(params.get('buffer_pp_r_init', []))
    Ts_in = params['Ts_in']
    Ts_out = params['Ts_out']
    Tss_in = params['Tss_in']
    Tss_out = params['Tss_out']
    Tsss_in = params['Tsss_in']
    Tsss_out = params['Tsss_out']
    temperature_fuel = initialS.copy()
    temperature_graphite = initialG.copy()

    # Initial plotting matrices
    rho_matrix = np.zeros((time_span, 1))
    phi_middle_matrix = np.zeros((time_span, 1))
    ci_middle_matrix = np.zeros((time_span, precursor_groups))
    temperature_fuel_middle_matrix = np.zeros((time_span, 1))
    temperature_graphite_middle_matrix = np.zeros((time_span, 1))
    rho_dt_matrix = np.zeros((time_span, 1))
    neutron_dt_matrix = np.zeros((time_span, 1))
    Ts_HX1_matrix = np.zeros((Nx, time_span))
    total_power_matrix = np.zeros((time_span, 1))
    time_axis = params['outer_dt'] * np.arange(time_span)
    system_diagnostics = {
        'time': time_axis,
        'core_inlet': np.zeros(time_span),
        'core_outlet': np.zeros(time_span),
        'hx1_hot_in': np.zeros(time_span),
        'hx1_hot_out': np.zeros(time_span),
        'hx1_cold_in': np.zeros(time_span),
        'hx1_cold_out': np.zeros(time_span),
        'hx2_hot_in': np.zeros(time_span),
        'hx2_hot_out': np.zeros(time_span),
        'hx2_cold_in': np.zeros(time_span),
        'hx2_cold_out': np.zeros(time_span),
        'brayton_T1': np.zeros(time_span),
        'brayton_T2': np.zeros(time_span),
        'brayton_T2r': np.zeros(time_span),
        'brayton_T3': np.zeros(time_span),
        'brayton_T4': np.zeros(time_span),
        'brayton_T4r': np.zeros(time_span),
        'brayton_W_c': np.zeros(time_span),
        'brayton_W_t': np.zeros(time_span),
        'brayton_W_net': np.zeros(time_span),
        'brayton_Q_in': np.zeros(time_span),
        'brayton_Q_out': np.zeros(time_span),
        'brayton_eta': np.zeros(time_span),
        'brayton_available_heat': np.zeros(time_span),
        'effective_beta': np.zeros(time_span),
        'effective_beta_group_1': np.zeros(time_span),
        'effective_beta_group_2': np.zeros(time_span),
        'effective_beta_group_3': np.zeros(time_span),
        'effective_beta_group_4': np.zeros(time_span),
        'effective_beta_group_5': np.zeros(time_span),
        'effective_beta_group_6': np.zeros(time_span),
        'reactivity_inserted_pcm': np.zeros(time_span),
        'feedback_reactivity_pcm': np.zeros(time_span),
        'feedback_fuel_delta_K': np.zeros(time_span),
        'feedback_graphite_delta_K': np.zeros(time_span),
        'first_law_residual': np.zeros(time_span),
        'core_power': np.zeros(time_span),
    }

    # Steps to save data (0, 1/3, 1/2, 2/3, 1 of total steps)
    save_steps = [0, time_span//3, time_span//2, 2*time_span//3, time_span-1]
    saved_data = []
    ci_groups_selected_step = None

    for step in range(time_span):
        if verbose and (step % max(int(log_every), 1) == 0 or step == time_span - 1):
            print(f'Step {step}/{time_span}')
        current_time = params['outer_dt'] * step
        external_reactivity = external_reactivity_from_schedule(params, current_time)

        state = {
            'temperature_fuel': temperature_fuel,
            'temperature_graphite': temperature_graphite,
            'rod_position': rod_position,
            'external_reactivity': external_reactivity,
        }
        y_n, q_prime = neutronics(y_n[:, -1], state, step, params)
        phi_fast = y_n[:N, -1].T
        phi_thermal = y_n[N:2 * N, -1].T
        phi = phi_fast + phi_thermal
        ci = y_n[2 * N:, -1].T
        phi_middle_matrix[step] = phi[mid_idx]
        if step > 0:
            neutron_dt_matrix[step] = (phi[mid_idx] - phi_middle_matrix[step - 1]) * 100
        total_power_matrix[step] = np.trapezoid(q_prime, params['z'])

        if step in save_steps:
            saved_data.append({
                'step': step,
                'fast_flux': phi_fast[mid_idx],
                'thermal_flux': phi_thermal[mid_idx],
                'neutron_flux': phi[mid_idx],
                'neutron_flux_change': neutron_dt_matrix[step]
            })

        ci_groups = ci.reshape(precursor_groups, N)
        ci_middle_matrix[step, :] = ci_groups[:, mid_idx]
        if step == selected_step:
            ci_groups_selected_step = ci_groups.copy()

        if params.get('core_inlet_mode', 'prescribed') == 'hx_coupled':
            Ts_core_0 = transport_delay(
                Ts_HX1_0,
                params['tau_hx_c'],
                Ts_in,
                buffer_hx_c,
                step,
                dt=params.get('outer_dt', 1.0),
            )
        else:
            Ts_core_0 = Ts_in
        y_th = thermal_hydraulics(y_th, q_prime, Ts_core_0, params, step)
        temperature_fuel = y_th[:N, -1].T
        temperature_graphite = y_th[N:, -1].T
        Ts_core_L = temperature_fuel[-1]
        temperature_fuel_middle_matrix[step] = temperature_fuel[mid_idx]
        temperature_graphite_middle_matrix[step] = temperature_graphite[mid_idx]

        Ts_HX1_L = transport_delay(
            Ts_core_L,
            params['tau_c_hx'],
            Ts_out,
            buffer_c_hx,
            step,
            dt=params.get('outer_dt', 1.0),
        )
        Tss_HX1_0 = transport_delay(
            Tss_HX2_0,
            params['tau_r_hx'],
            Tss_in,
            buffer_r_hx,
            step,
            dt=params.get('outer_dt', 1.0),
        )
        y_hx1 = HX1(y_hx1, Ts_HX1_L, Tss_HX1_0, params, step)
        Ts_HX1 = y_hx1[:Nx, -1]
        Tss_HX1 = y_hx1[Nx:, -1]
        Ts_HX1_0 = Ts_HX1[0]
        Tss_HX1_L = Tss_HX1[-1]

        Ts_HX1_matrix[:, step] = Ts_HX1

        Tss_HX2_L = transport_delay(
            Tss_HX1_L,
            params['tau_hx_r'],
            Tss_out,
            buffer_hx_r,
            step,
            dt=params.get('outer_dt', 1.0),
        )
        Tsss_HX2_0 = transport_delay(
            Tsss_pp_0,
            params['tau_pp_r'],
            Tsss_in,
            buffer_pp_r,
            step,
            dt=params.get('outer_dt', 1.0),
        )
        y_hx2 = HX2(y_hx2, Tss_HX2_L, Tsss_HX2_0, params, step)
        Tss_HX2 = y_hx2[:Nx, -1]
        Tsss_HX2 = y_hx2[Nx:, -1]
        Tss_HX2_0 = Tss_HX2[0]
        Tsss_HX2_L = Tsss_HX2[-1]

        Tsss_pp_L = transport_delay(
            Tsss_HX2_L,
            params['tau_r_pp'],
            Tsss_out,
            buffer_r_pp,
            step,
            dt=params.get('outer_dt', 1.0),
        )
        params['brayton_available_heat_W'] = float(total_power_matrix[step, 0])
        y_pp = power_plant_temp(Tsss_pp_L, params, step)
        Tsss_pp_0 = y_pp
        pp_state = params.get('last_power_plant', {})

        system_diagnostics['core_inlet'][step] = Ts_core_0
        system_diagnostics['core_outlet'][step] = Ts_core_L
        system_diagnostics['hx1_hot_in'][step] = Ts_HX1_L
        system_diagnostics['hx1_hot_out'][step] = Ts_HX1_0
        system_diagnostics['hx1_cold_in'][step] = Tss_HX1_0
        system_diagnostics['hx1_cold_out'][step] = Tss_HX1_L
        system_diagnostics['hx2_hot_in'][step] = Tss_HX2_L
        system_diagnostics['hx2_hot_out'][step] = Tss_HX2_0
        system_diagnostics['hx2_cold_in'][step] = Tsss_HX2_0
        system_diagnostics['hx2_cold_out'][step] = Tsss_HX2_L
        system_diagnostics['core_power'][step] = total_power_matrix[step, 0]
        system_diagnostics['effective_beta'][step] = params.get('last_effective_beta', 0.0)
        beta_groups = np.asarray(params.get('last_effective_beta_groups', np.zeros(6)), dtype=float)
        for group_idx in range(min(6, beta_groups.size)):
            system_diagnostics[f'effective_beta_group_{group_idx + 1}'][step] = beta_groups[group_idx]
        system_diagnostics['reactivity_inserted_pcm'][step] = external_reactivity * 1.0e5
        system_diagnostics['feedback_reactivity_pcm'][step] = params.get('last_feedback_rho_pcm', 0.0)
        system_diagnostics['feedback_fuel_delta_K'][step] = params.get('last_feedback_fuel_delta_K', 0.0)
        system_diagnostics['feedback_graphite_delta_K'][step] = params.get('last_feedback_graphite_delta_K', 0.0)
        for key in ('T1', 'T2', 'T2r', 'T3', 'T4', 'T4r', 'W_c', 'W_t', 'W_net', 'Q_in', 'Q_out', 'eta_b'):
            if key in pp_state:
                target = 'brayton_eta' if key == 'eta_b' else f'brayton_{key}'
                system_diagnostics[target][step] = pp_state[key]
        if 'available_heat' in pp_state:
            system_diagnostics['brayton_available_heat'][step] = pp_state['available_heat']
            system_diagnostics['first_law_residual'][step] = (
                total_power_matrix[step, 0] - pp_state['Q_in']
            )

        rho = np.full(N, external_reactivity)
        rho_matrix[step] = rho.mean()
        if step > 0:
            rho_dt_matrix[step] = rho.mean() - rho_matrix[step - 1]

    # Plotting results including Ts_HX1
    plot_results(z=np.linspace(0, params['L'], N),
                 phi=phi,
                 ci=ci,
                 rho=rho,
                 rho_matrix=rho_matrix,
                 temperature_fuel=temperature_fuel,
                 temperature_graphite=temperature_graphite,
                 Ts_HX1_matrix=Ts_HX1_matrix,
                 Tss_HX1=Tss_HX1,
                 Tss_HX2=Tss_HX2,
                 Tsss_HX2=Tsss_HX2,
                 phi_middle_matrix=phi_middle_matrix,
                 temperature_fuel_middle_matrix=temperature_fuel_middle_matrix,
                 temperature_graphite_middle_matrix=temperature_graphite_middle_matrix,
                 ci_middle_matrix=ci_middle_matrix,
                 rho_dt_matrix=rho_dt_matrix,
                 neutron_dt_matrix=neutron_dt_matrix,
                 total_power_matrix=total_power_matrix,
                 system_diagnostics=system_diagnostics,
                 index=index)

    saved_data.append({
                'neutron_velocity': params['neutron_velocity'],
                'D_ref_mean': params['D_ref'].mean(axis=1),
                'sigma_a_ref_mean': params['sigma_a_ref'].mean(axis=1),
                'nu_sigma_f_ref_mean': params['nu_sigma_f_ref'].mean(axis=1),
                'scale': params['scale'],
                'steady_state_summary': params.get('steady_state_summary', {}),
            })
    
    # Save specific data points
    save_specific_data(saved_data, index)
    save_ci_groups_csv(selected_step, ci_groups_selected_step, params, index)
    save_system_diagnostics(system_diagnostics, index)
    return {
        'time': time_axis.copy(),
        'phi_middle': phi_middle_matrix.copy(),
        'ci_middle': ci_middle_matrix.copy(),
        'temperature_fuel_middle': temperature_fuel_middle_matrix.copy(),
        'temperature_graphite_middle': temperature_graphite_middle_matrix.copy(),
        'total_power': total_power_matrix.copy(),
        'system_diagnostics': {key: np.asarray(value).copy() for key, value in system_diagnostics.items()},
    }

def plot_results(z, phi, ci, rho, rho_matrix, temperature_fuel, temperature_graphite,
                 Ts_HX1_matrix, Tss_HX1, Tss_HX2, Tsss_HX2, phi_middle_matrix,
                 temperature_fuel_middle_matrix, temperature_graphite_middle_matrix,
                 ci_middle_matrix, rho_dt_matrix, neutron_dt_matrix, total_power_matrix,
                 system_diagnostics, index):
    if plt is None:
        return

    os.makedirs('simulation_results', exist_ok=True)
    plot_dir = f'simulation_results/plots_{index}'
    os.makedirs(plot_dir, exist_ok=True)

    # First plot: Neutron flux and delayed neutron precursors
    fig, ax = plt.subplots(2, 2, figsize=(14, 6))
    ax[0, 0].plot(z, phi)
    ax[0, 0].set_title('Neutron Flux')

    precursor_groups = ci_middle_matrix.shape[1]
    for i in range(precursor_groups):
        ax[0, 1].plot(z, ci[i * len(z):(i + 1) * len(z)], label=f'Ci{i + 1}')
        ax[0, 1].legend()
    ax[0, 1].set_title('Delayed Neutron Precursors')

    ax[1, 0].plot(rho_matrix * 1e5, label='Reactivity at middle with time(pcm)')
    ax[1, 0].set_title('Reactivity')

    ax[1, 1].plot(z, temperature_fuel, label='Fuel')
    ax[1, 1].plot(z, temperature_graphite, label='Graphite')
    ax[1, 1].legend()
    ax[1, 1].set_title('Temperature in the core')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/neutron_flux_and_precursors.png')
    plt.close(fig)

    # Second plot: Temperature in the heat exchangers
    fig, ax = plt.subplots(2, 2, figsize=(14, 6))
    ax[0, 0].plot(z, Ts_HX1_matrix[:, -1], label='Salt')
    ax[0, 0].plot(z, Tss_HX1, label='Coolant')
    ax[0, 0].legend()
    ax[0, 0].set_title('Temperature in the heat exchanger 1')

    ax[0, 1].plot(z, Tss_HX2, label='Tss')
    ax[0, 1].plot(z, Tsss_HX2, label='Tsss')
    ax[0, 1].legend()
    ax[0, 1].set_title('Temperature in the heat exchanger 2')

    ax[1, 0].plot(phi_middle_matrix)
    ax[1, 0].set_title('Neutron Flux with time in the middle')

    ax[1, 1].plot(temperature_fuel_middle_matrix)
    ax[1, 1].set_title('Temperature in the core with time in the middle')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/temperature_in_heat_exchangers.png')
    plt.close(fig)

    # Third plot: Delayed Neutron Precursors with time in the middle
    fig, ax = plt.subplots(figsize=(14, 6))
    for i in range(precursor_groups):
        ax.plot(ci_middle_matrix[:, i], label=f'Ci{i + 1}')
        ax.legend()
    ax.set_title('Delayed Neutron Precursors with time in the middle')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/precursors_with_time_middle.png')
    plt.close(fig)

    # Fourth plot: Reactivity and neutron flux change
    fig, ax = plt.subplots(2, 2, figsize=(14, 6))
    ax[0, 0].plot(rho_dt_matrix * 1e5, label='Reactivity change (pcm)')
    ax[0, 0].set_title('Reactivity_dt')

    ax[0, 1].plot(z, rho * 1e5, label='Reactivity')
    ax[0, 1].set_title('Reactivity')

    ax[1, 0].plot(neutron_dt_matrix, label='Neutron flux change')
    ax[1, 0].set_title('Neutron flux_dt * 100')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/rho_dt.png')
    plt.close(fig)

    fig, ax = plt.subplots(2, 2, figsize=(15, 8))
    time = system_diagnostics['time']
    ax[0, 0].plot(time, system_diagnostics['core_inlet'], label='Core Inlet')
    ax[0, 0].plot(time, system_diagnostics['core_outlet'], label='Core Outlet')
    ax[0, 0].plot(time, system_diagnostics['hx1_hot_out'], label='HX1 Salt Outlet')
    ax[0, 0].legend()
    ax[0, 0].set_title('Primary Loop Temperatures')

    ax[0, 1].plot(time, system_diagnostics['hx1_cold_in'], label='HX1 Secondary Inlet')
    ax[0, 1].plot(time, system_diagnostics['hx1_cold_out'], label='HX1 Secondary Outlet')
    ax[0, 1].plot(time, system_diagnostics['hx2_hot_out'], label='HX2 Secondary Return')
    ax[0, 1].legend()
    ax[0, 1].set_title('Secondary Loop Temperatures')

    ax[1, 0].plot(time, system_diagnostics['hx2_cold_in'], label='HX2 Brayton Inlet')
    ax[1, 0].plot(time, system_diagnostics['hx2_cold_out'], label='HX2 Brayton Outlet')
    ax[1, 0].plot(time, system_diagnostics['brayton_T2r'], label='Brayton Return')
    ax[1, 0].legend()
    ax[1, 0].set_title('Tertiary Loop Temperatures')

    ax[1, 1].plot(time, temperature_fuel_middle_matrix, label='Fuel Midplane')
    ax[1, 1].plot(time, temperature_graphite_middle_matrix, label='Graphite Midplane')
    ax[1, 1].plot(time, total_power_matrix, label='Core Power')
    ax[1, 1].legend()
    ax[1, 1].set_title('Core Midplane Response')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/system_loop_response.png')
    plt.close(fig)

    fig, ax = plt.subplots(2, 2, figsize=(15, 8))
    ax[0, 0].plot(time, system_diagnostics['brayton_T1'], label='T1')
    ax[0, 0].plot(time, system_diagnostics['brayton_T2'], label='T2')
    ax[0, 0].plot(time, system_diagnostics['brayton_T2r'], label='T2r')
    ax[0, 0].legend()
    ax[0, 0].set_title('Compressor and Recuperator')

    ax[0, 1].plot(time, system_diagnostics['brayton_T3'], label='T3')
    ax[0, 1].plot(time, system_diagnostics['brayton_T4'], label='T4')
    ax[0, 1].plot(time, system_diagnostics['brayton_T4r'], label='T4r')
    ax[0, 1].legend()
    ax[0, 1].set_title('Turbine Side Temperatures')

    ax[1, 0].plot(time, system_diagnostics['brayton_W_c'], label='Compressor Work')
    ax[1, 0].plot(time, system_diagnostics['brayton_W_t'], label='Turbine Work')
    ax[1, 0].plot(time, system_diagnostics['brayton_W_net'], label='Net Work')
    ax[1, 0].legend()
    ax[1, 0].set_title('Brayton Work Balance')

    ax[1, 1].plot(time, system_diagnostics['brayton_Q_in'], label='Q_in')
    ax[1, 1].plot(time, system_diagnostics['brayton_Q_out'], label='Q_out')
    ax[1, 1].plot(time, system_diagnostics['brayton_eta'], label='Efficiency')
    ax[1, 1].legend()
    ax[1, 1].set_title('Brayton Heat Balance')

    plt.tight_layout()
    plt.savefig(f'{plot_dir}/brayton_diagnostics.png')
    plt.close(fig)

def save_specific_data(data, index):
    print(f'Saving specific data for simulation {index}')
    os.makedirs('simulation_results', exist_ok=True)
    data_file = f'simulation_results/specific_data_{index}.npz'
    np.savez(data_file, data=data)

def save_system_diagnostics(system_diagnostics, index):
    os.makedirs('simulation_results', exist_ok=True)
    np.savez(f'simulation_results/system_diagnostics_{index}.npz', **system_diagnostics)

def main():
    run_simulation(generate_parameters(), 0)
    # Define ranges of values for parameters
    # V_values = np.linspace(1.103497e6, 1.103497e8, 5)
    # D_values = np.linspace(0.96343*7, 0.96343*8, 5)     
    # sigma_a_values=np.linspace(0.002161937, 0.002161940, 30) # cm^-1        
    # nu_sigma_f_values = np.linspace(3.33029e-2/7, 3.33029e-2/8, 5) # cm^-1
    # L=22.9
    # phi_0_values = np.linspace(1 * np.ones(200), 1e10*np.ones(200), 10)
    # rho_init_values = np.linspace(-3e-5, 3e-5, 100)
    # scale_values = [0, 1e-1, 1e-2, 1e-3, 1e-4]
    # bc_s0_values = np.linspace(900, 940, 10)
    # bc_sL_values = np.linspace(930, 990, 10)
    # bc_g0_values = np.linspace(910, 950, 10)
    # bc_gL_values = np.linspace(940, 1000, 10)
    U_values = np.linspace(10000, 36000, 10)

    # Generate parameter sets
    parameter_sets = [
        # generate_parameters(U=U) 
        # for U in U_values
        # for rho_init in rho_init_values
        # for V in V_values
        # for D in D_values
        # for sigma_a in sigma_a_values
        # for nu_sigma_f in nu_sigma_f_values
        # for phi_0 in phi_0_values
        # for scale in scale_values
        # for bc_s0 in bc_s0_values
        # for bc_sL in bc_sL_values
        # for bc_g0 in bc_g0_values
        # for bc_gL in bc_gL_values
    ]

    # Run simulations in parallel
    # Parallel(n_jobs=-1)(delayed(run_simulation)(params, idx) for idx, params in enumerate(parameter_sets))

if __name__ == "__main__":
    main()
