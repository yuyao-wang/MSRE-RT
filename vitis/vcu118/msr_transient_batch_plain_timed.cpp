#include <algorithm>
#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#define main msr_plain_embedded_main
#include "../../cpp/msr_plain.cpp"
#undef main

#include "../msr_vitis_kernel.cpp"

namespace {

template <typename T>
std::vector<T> read_blob_array(const std::string& path, std::size_t count) {
    static_assert(std::is_trivially_copyable<T>::value, "blob type must be trivially copyable");
    std::vector<T> values(count);
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("failed to open " + path);
    }
    input.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(sizeof(T) * count));
    if (input.gcount() != static_cast<std::streamsize>(sizeof(T) * count)) {
        throw std::runtime_error("short read for " + path);
    }
    return values;
}

template <typename T>
void write_blob_array(const std::string& path, const std::vector<T>& values) {
    static_assert(std::is_trivially_copyable<T>::value, "blob type must be trivially copyable");
    std::ofstream output(path, std::ios::binary);
    if (!output) {
        throw std::runtime_error("failed to open output " + path);
    }
    output.write(reinterpret_cast<const char*>(values.data()), static_cast<std::streamsize>(sizeof(T) * values.size()));
    if (!output) {
        throw std::runtime_error("failed to write " + path);
    }
}

template <typename T>
std::vector<T> read_scalar_array(const std::string& path, std::size_t count) {
    return read_blob_array<T>(path, count);
}

struct TimingStats {
    double min_us = std::numeric_limits<double>::max();
    double max_us = 0.0;
    double sum_us = 0.0;
};

void update_stats(TimingStats& stats, double sample_us) {
    stats.min_us = std::min(stats.min_us, sample_us);
    stats.max_us = std::max(stats.max_us, sample_us);
    stats.sum_us += sample_us;
}

double avg_us(const TimingStats& stats, int repeats) {
    return repeats > 0 ? stats.sum_us / static_cast<double>(repeats) : 0.0;
}

int wrap_index(int idx, int size) {
    while (idx < 0) {
        idx += size;
    }
    while (idx >= size) {
        idx -= size;
    }
    return idx;
}

template <typename SrcT>
void copy_fixed_vector_to_std(const SrcT* src, int n, std::vector<double>& dst) {
    dst.resize(static_cast<std::size_t>(n));
    for (int idx = 0; idx < n; ++idx) {
        dst[static_cast<std::size_t>(idx)] = static_cast<double>(src[idx]);
    }
}

template <typename SrcT, std::size_t N>
void copy_fixed_vector_to_array(const SrcT* src, std::array<double, N>& dst) {
    for (std::size_t idx = 0; idx < N; ++idx) {
        dst[idx] = static_cast<double>(src[idx]);
    }
}

template <std::size_t Rows>
void copy_history_outlet(
    const double src[Rows],
    std::array<double, Rows>& dst
) {
    for (std::size_t idx = 0; idx < Rows; ++idx) {
        dst[idx] = src[idx];
    }
}

std::deque<double> delay_line_to_deque(const msr_vitis::DelayLine& line) {
    std::deque<double> values;
    for (int offset = 0; offset < line.size; ++offset) {
        const int idx = wrap_index(line.head + offset, msr_vitis::kMaxDelaySlots);
        values.push_back(line.data[idx]);
    }
    return values;
}

msr::PrecursorLoopState precursor_history_to_loop_state(
    const msr_vitis::PrecursorHistory& history,
    double outer_dt
) {
    msr::PrecursorLoopState state;
    copy_fixed_vector_to_array(history.last_outlet, state.last_outlet);

    int valid_count = history.valid_count;
    if (valid_count <= 0) {
        state.times.push_back(0.0);
        state.outlets.push_back(state.last_outlet);
        return state;
    }
    if (valid_count > msr_vitis::kMaxLoopHistory) {
        valid_count = msr_vitis::kMaxLoopHistory;
    }

    const int start = history.write_index - valid_count;
    for (int pos = 0; pos < valid_count; ++pos) {
        const int idx = wrap_index(start + pos, msr_vitis::kMaxLoopHistory);
        const double sample_time = static_cast<double>(pos - valid_count + 1) * outer_dt;
        std::array<double, msr::kPrecursorGroups> outlet{};
        for (int group = 0; group < msr::kPrecursorGroups; ++group) {
            outlet[group] = history.outlet_history[group][idx];
        }
        state.times.push_back(sample_time);
        state.outlets.push_back(outlet);
    }
    state.last_outlet = state.outlets.back();
    return state;
}

void precursor_loop_state_to_history(
    const msr::PrecursorLoopState& loop_state,
    msr_vitis::PrecursorHistory& history
) {
    for (int group = 0; group < msr::kPrecursorGroups; ++group) {
        for (int idx = 0; idx < msr_vitis::kMaxLoopHistory; ++idx) {
            history.outlet_history[group][idx] = 0.0;
        }
        history.last_outlet[group] = loop_state.last_outlet[group];
    }

    const int total_count = static_cast<int>(loop_state.outlets.size());
    const int valid_count = std::min(total_count, msr_vitis::kMaxLoopHistory);
    const int first = total_count - valid_count;
    for (int pos = 0; pos < valid_count; ++pos) {
        const auto& outlet = loop_state.outlets[static_cast<std::size_t>(first + pos)];
        for (int group = 0; group < msr::kPrecursorGroups; ++group) {
            history.outlet_history[group][pos] = outlet[group];
        }
    }
    history.write_index = valid_count % msr_vitis::kMaxLoopHistory;
    history.valid_count = valid_count;
}

std::string inlet_mode_to_string(int mode) {
    switch (mode) {
        case msr_vitis::kInletFresh:
            return "fresh";
        case msr_vitis::kInletCopy:
            return "copy";
        case msr_vitis::kInletRecirculate:
        default:
            return "recirculate";
    }
}

std::string core_inlet_mode_to_string(int mode) {
    switch (mode) {
        case msr_vitis::kCoreInletHxCoupled:
            return "hx_coupled";
        case msr_vitis::kCoreInletPrescribed:
        default:
            return "prescribed";
    }
}

std::string external_reactivity_mode_to_string(int mode) {
    switch (mode) {
        case msr_vitis::kExternalReactivityAbsorption:
            return "absorption";
        case msr_vitis::kExternalReactivityFissionSource:
        default:
            return "fission_source";
    }
}

void load_parameters_from_kernel(const msr_vitis::KernelParams& src, msr::Parameters& dst) {
    dst.N = src.N;
    dst.Nx = src.Nx;
    dst.neutronics_state_size = (msr::kEnergyGroups + msr::kPrecursorGroups) * src.N;
    dst.z.resize(static_cast<std::size_t>(src.N));
    for (int idx = 0; idx < src.N; ++idx) {
        dst.z[static_cast<std::size_t>(idx)] = src.z[idx];
    }
    dst.L = (src.N > 1) ? (src.z[src.N - 1] - src.z[0]) : src.dz;
    dst.dz = src.dz;
    dst.dx = (src.Nx > 1) ? (dst.L / static_cast<double>(src.Nx - 1)) : dst.L;
    dst.outer_dt = src.outer_dt;
    dst.ode_horizon = src.outer_dt;
    dst.nominal_total_power = src.brayton_available_heat_W;
    dst.brayton_available_heat_W = src.brayton_available_heat_W;

    dst.v_core = src.u_core;
    dst.u_core = src.u_core;
    dst.u_precursor = src.u_precursor;
    dst.inlet_mode = inlet_mode_to_string(src.inlet_mode);
    dst.core_inlet_mode = core_inlet_mode_to_string(src.core_inlet_mode);
    dst.use_graphite_axial_conduction = (src.use_graphite_axial_conduction != 0);
    dst.point_kinetics_enabled = (src.point_kinetics_enabled != 0);
    dst.external_reactivity_mode = external_reactivity_mode_to_string(src.external_reactivity_mode);

    copy_fixed_vector_to_array(src.neutron_velocity, dst.neutron_velocity);
    copy_fixed_vector_to_array(src.beta, dst.beta);
    copy_fixed_vector_to_array(src.lambda_i, dst.lambda_i);
    copy_fixed_vector_to_array(src.nu, dst.nu);
    copy_fixed_vector_to_array(src.chi_p, dst.chi_p);
    copy_fixed_vector_to_array(src.chi_d, dst.chi_d);
    copy_fixed_vector_to_array(src.d_e, dst.d_e);
    copy_fixed_vector_to_array(src.rod_sigma_a_amplitude, dst.rod_sigma_a_amplitude);
    copy_fixed_vector_to_array(src.external_reactivity_to_absorption, dst.external_reactivity_to_absorption);
    dst.Beta = src.Beta;
    dst.power_scale = src.power_scale;
    dst.reference_multiplication_ratio = src.reference_multiplication_ratio;
    dst.critical_fission_scale = src.critical_fission_scale;
    dst.prompt_generation_time_s = src.prompt_generation_time_s;
    dst.last_global_rho = src.external_reactivity;
    dst.precursor_loop_efficiency = src.precursor_loop_efficiency;
    dst.precursor_loop_tau = src.precursor_loop_tau;
    dst.tau_l = src.precursor_loop_tau;

    for (int group = 0; group < msr::kEnergyGroups; ++group) {
        copy_fixed_vector_to_std(src.D_ref[group], src.N, dst.D_ref[group]);
        copy_fixed_vector_to_std(src.sigma_a_ref[group], src.N, dst.sigma_a_ref[group]);
        copy_fixed_vector_to_std(src.nu_sigma_f_ref[group], src.N, dst.nu_sigma_f_ref[group]);
        copy_fixed_vector_to_std(src.rod_shape[group], src.N, dst.rod_shape[group]);
        copy_fixed_vector_to_std(src.a_sigma_a_s[group], src.N, dst.a_sigma_a_s[group]);
        copy_fixed_vector_to_std(src.a_sigma_a_gr[group], src.N, dst.a_sigma_a_gr[group]);
        copy_fixed_vector_to_std(src.a_nu_sigma_f_s[group], src.N, dst.a_nu_sigma_f_s[group]);
        copy_fixed_vector_to_std(src.a_nu_sigma_f_gr[group], src.N, dst.a_nu_sigma_f_gr[group]);
        copy_fixed_vector_to_std(src.a_D_s[group], src.N, dst.a_D_s[group]);
        copy_fixed_vector_to_std(src.a_D_gr[group], src.N, dst.a_D_gr[group]);
        copy_fixed_vector_to_std(src.transverse_buckling_sq[group], src.N, dst.transverse_buckling_sq[group]);
        dst.sigma_f_ref[group].resize(static_cast<std::size_t>(src.N));
        for (int idx = 0; idx < src.N; ++idx) {
            dst.sigma_f_ref[group][static_cast<std::size_t>(idx)] =
                src.nu_sigma_f_ref[group][idx] / std::max(src.nu[group], 1.0e-12);
        }
    }

    copy_fixed_vector_to_std(src.sigma_s12_ref, src.N, dst.sigma_s12_ref);
    copy_fixed_vector_to_std(src.a_sigma_s12_s, src.N, dst.a_sigma_s12_s);
    copy_fixed_vector_to_std(src.a_sigma_s12_gr, src.N, dst.a_sigma_s12_gr);
    copy_fixed_vector_to_std(src.T_s_ref, src.N, dst.T_s_ref);
    copy_fixed_vector_to_std(src.T_gr_ref, src.N, dst.T_gr_ref);
    copy_fixed_vector_to_std(src.phi1_ref, src.N, dst.phi_1_0);
    copy_fixed_vector_to_std(src.phi2_ref, src.N, dst.phi_2_0);
    copy_fixed_vector_to_std(src.A_f, src.N, dst.A_f);
    dst.phi_0 = dst.phi_1_0;
    dst.phi_0.insert(dst.phi_0.end(), dst.phi_2_0.begin(), dst.phi_2_0.end());

    dst.min_diffusion = src.min_diffusion;
    dst.min_cross_section = src.min_cross_section;

    dst.rho_s = src.rho_s;
    dst.c_p_s = src.c_p_s;
    dst.A_s = src.A_s;
    dst.rho_gr = src.rho_gr;
    dst.c_p_g = src.c_p_g;
    dst.A_gr = src.A_gr;
    dst.h_sgr = src.h_sgr;
    dst.P_sgr = src.P_sgr;
    dst.k_gr = src.k_gr;
    dst.eta_s = src.eta_s;
    dst.eta_gr = src.eta_gr;
    dst.err = src.err;
    dst.bc_s0 = src.bc_s0;
    dst.bc_sL = src.Ts_out;
    dst.bc_g0 = src.T_gr_ref[0];
    dst.bc_gL = src.T_gr_ref[src.N - 1];

    dst.L_HX = src.hx1_dx * static_cast<double>(std::max(src.Nx - 1, 1));
    dst.V_he_s = -src.hx1_hot_velocity;
    dst.V_he_ss = src.hx1_cold_velocity;
    dst.U_hx = 1.0;
    dst.M_he_s = (src.hx1_hot_exchange_coeff > 0.0)
        ? (dst.U_hx / std::max(src.hx1_hot_exchange_coeff * dst.c_p_s, 1.0e-12))
        : 1.0;
    dst.c_p_ss = 1.0;
    dst.M_he_ss = (src.hx1_cold_exchange_coeff > 0.0)
        ? (dst.U_hx / std::max(src.hx1_cold_exchange_coeff * dst.c_p_ss, 1.0e-12))
        : 1.0;

    dst.L_HX2 = src.hx2_dx * static_cast<double>(std::max(src.Nx - 1, 1));
    dst.V_he2_s = -src.hx2_hot_velocity;
    dst.V_he2_ss = src.hx2_cold_velocity;
    dst.U2_hx = 1.0;
    dst.M_he2_s = (src.hx2_hot_exchange_coeff > 0.0)
        ? (dst.U2_hx / std::max(src.hx2_hot_exchange_coeff * dst.c_p_ss, 1.0e-12))
        : 1.0;
    dst.c_p_sss = src.c_p_sss;
    dst.M_he2_ss = (src.hx2_cold_exchange_coeff > 0.0)
        ? (dst.U2_hx / std::max(src.hx2_cold_exchange_coeff * dst.c_p_sss, 1.0e-12))
        : 1.0;

    dst.Ts_in = src.Ts_in;
    dst.Ts_out = src.Ts_out;
    dst.Tss_in = src.Tss_in;
    dst.Tss_out = src.Tss_out;
    dst.Tsss_in = src.Tsss_in;
    dst.Tsss_out = src.Tsss_out;

    dst.brayton_gamma = src.brayton_gamma;
    dst.brayton_eta_c = src.brayton_eta_c;
    dst.brayton_eta_t = src.brayton_eta_t;
    dst.brayton_pi_c = src.brayton_pi_c;
    dst.brayton_pi_t = src.brayton_pi_t;
    dst.brayton_recuperator_efficiency = src.brayton_recuperator_efficiency;
    dst.brayton_cooler_outlet_temp = src.brayton_cooler_outlet_temp;
    dst.brayton_min_heater_approach = src.brayton_min_heater_approach;
    dst.brayton_mdot = src.brayton_mdot;
}

void load_state_from_kernel(
    const msr_vitis::StepState& src,
    const msr_vitis::DelayBundle& delays,
    const msr_vitis::KernelParams& kernel_params,
    msr::Parameters& params,
    std::vector<double>& y_n,
    std::vector<double>& y_th,
    std::vector<double>& y_hx1,
    std::vector<double>& y_hx2,
    double& Ts_HX1_0,
    double& Tss_HX2_0,
    double& Tsss_pp_0
) {
    std::vector<double> phi1;
    std::vector<double> phi2;
    copy_fixed_vector_to_std(src.phi1, kernel_params.N, phi1);
    copy_fixed_vector_to_std(src.phi2, kernel_params.N, phi2);
    std::array<std::vector<double>, msr::kPrecursorGroups> C;
    for (int group = 0; group < msr::kPrecursorGroups; ++group) {
        copy_fixed_vector_to_std(src.C[group], kernel_params.N, C[group]);
    }
    y_n = msr::PackNeutronicsState(phi1, phi2, C);

    copy_fixed_vector_to_std(src.fuel, kernel_params.N, params.initialS);
    copy_fixed_vector_to_std(src.graphite, kernel_params.N, params.initialG);
    y_th = msr::PackThermalState(params.initialS, params.initialG);

    std::vector<double> hx1_hot;
    std::vector<double> hx1_cold;
    std::vector<double> hx2_hot;
    std::vector<double> hx2_cold;
    copy_fixed_vector_to_std(src.hx1_hot, kernel_params.Nx, hx1_hot);
    copy_fixed_vector_to_std(src.hx1_cold, kernel_params.Nx, hx1_cold);
    copy_fixed_vector_to_std(src.hx2_hot, kernel_params.Nx, hx2_hot);
    copy_fixed_vector_to_std(src.hx2_cold, kernel_params.Nx, hx2_cold);

    y_hx1 = hx1_hot;
    y_hx1.insert(y_hx1.end(), hx1_cold.begin(), hx1_cold.end());
    y_hx2 = hx2_hot;
    y_hx2.insert(y_hx2.end(), hx2_cold.begin(), hx2_cold.end());

    params.kinetics_amplitude = src.kinetics_amplitude;
    copy_fixed_vector_to_array(src.kinetics_precursors, params.kinetics_precursors);
    copy_fixed_vector_to_array(src.kinetics_beta_effective, params.kinetics_beta_effective);
    params.last_effective_beta = std::accumulate(
        params.kinetics_beta_effective.begin(),
        params.kinetics_beta_effective.end(),
        0.0
    );
    params.last_neutron_amplitude = src.kinetics_amplitude;
    params.precursor_loop_state = precursor_history_to_loop_state(src.precursor_history, kernel_params.outer_dt);

    params.buffer_hx_c_init = delay_line_to_deque(delays.hx_c);
    params.buffer_c_hx_init = delay_line_to_deque(delays.c_hx);
    params.buffer_r_hx_init = delay_line_to_deque(delays.r_hx);
    params.buffer_hx_r_init = delay_line_to_deque(delays.hx_r);
    params.buffer_r_pp_init = delay_line_to_deque(delays.r_pp);
    params.buffer_pp_r_init = delay_line_to_deque(delays.pp_r);

    Ts_HX1_0 = src.Ts_HX1_0;
    Tss_HX2_0 = src.Tss_HX2_0;
    Tsss_pp_0 = src.Tsss_pp_0;
}

void store_state_to_kernel(
    const msr::Parameters& params,
    const std::vector<double>& y_n,
    const std::vector<double>& y_th,
    const std::vector<double>& y_hx1,
    const std::vector<double>& y_hx2,
    double Ts_HX1_0,
    double Tss_HX2_0,
    double Tsss_pp_0,
    msr_vitis::StepState& dst
) {
    std::vector<double> phi1;
    std::vector<double> phi2;
    std::array<std::vector<double>, msr::kPrecursorGroups> C;
    msr::UnpackNeutronicsState(y_n, params.N, phi1, phi2, C);

    for (int idx = 0; idx < params.N; ++idx) {
        dst.phi1[idx] = phi1[static_cast<std::size_t>(idx)];
        dst.phi2[idx] = phi2[static_cast<std::size_t>(idx)];
        dst.fuel[idx] = y_th[static_cast<std::size_t>(idx)];
        dst.graphite[idx] = y_th[static_cast<std::size_t>(params.N + idx)];
    }
    for (int group = 0; group < msr::kPrecursorGroups; ++group) {
        for (int idx = 0; idx < params.N; ++idx) {
            dst.C[group][idx] = C[group][static_cast<std::size_t>(idx)];
        }
    }
    dst.kinetics_amplitude = params.kinetics_amplitude;
    for (int group = 0; group < msr::kPrecursorGroups; ++group) {
        dst.kinetics_precursors[group] = params.kinetics_precursors[group];
        dst.kinetics_beta_effective[group] = params.kinetics_beta_effective[group];
    }
    for (int idx = 0; idx < params.Nx; ++idx) {
        dst.hx1_hot[idx] = y_hx1[static_cast<std::size_t>(idx)];
        dst.hx1_cold[idx] = y_hx1[static_cast<std::size_t>(params.Nx + idx)];
        dst.hx2_hot[idx] = y_hx2[static_cast<std::size_t>(idx)];
        dst.hx2_cold[idx] = y_hx2[static_cast<std::size_t>(params.Nx + idx)];
    }
    dst.Ts_HX1_0 = Ts_HX1_0;
    dst.Tss_HX2_0 = Tss_HX2_0;
    dst.Tsss_pp_0 = Tsss_pp_0;
    precursor_loop_state_to_history(params.precursor_loop_state, dst.precursor_history);
}

struct ScenarioResult {
    msr_vitis::StepState final_state{};
    msr_vitis::StepDiagnostics final_diag{};
};

ScenarioResult run_plain_scenario(
    const msr_vitis::StepState& input_state,
    const msr_vitis::DelayBundle& input_delays,
    const msr_vitis::KernelParams& kernel_params,
    const double* rod_positions,
    const double* external_reactivities,
    int step_count
) {
    msr::Parameters params;
    load_parameters_from_kernel(kernel_params, params);

    std::vector<double> y_n;
    std::vector<double> y_th;
    std::vector<double> y_hx1;
    std::vector<double> y_hx2;
    double Ts_HX1_0 = 0.0;
    double Tss_HX2_0 = 0.0;
    double Tsss_pp_0 = 0.0;
    load_state_from_kernel(
        input_state,
        input_delays,
        kernel_params,
        params,
        y_n,
        y_th,
        y_hx1,
        y_hx2,
        Ts_HX1_0,
        Tss_HX2_0,
        Tsss_pp_0
    );

    std::deque<double> buffer_hx_c = params.buffer_hx_c_init;
    std::deque<double> buffer_c_hx = params.buffer_c_hx_init;
    std::deque<double> buffer_r_hx = params.buffer_r_hx_init;
    std::deque<double> buffer_hx_r = params.buffer_hx_r_init;
    std::deque<double> buffer_r_pp = params.buffer_r_pp_init;
    std::deque<double> buffer_pp_r = params.buffer_pp_r_init;

    std::vector<double> temperature_fuel = params.initialS;
    std::vector<double> temperature_graphite = params.initialG;
    std::vector<double> q_prime(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> phi_1;
    std::vector<double> phi_2;
    std::array<std::vector<double>, msr::kPrecursorGroups> C;

    msr_vitis::StepDiagnostics final_diag{};
    const int mid_idx = params.N / 2;
    for (int step = 0; step < step_count; ++step) {
        const double external_reactivity = external_reactivities[step];
        const double rod_position = rod_positions[step];
        const auto neutronics = msr::SolveNeutronics(
            params,
            y_n,
            temperature_fuel,
            temperature_graphite,
            rod_position,
            external_reactivity,
            step
        );
        y_n = neutronics.y_n;
        q_prime = neutronics.q_prime;
        msr::UnpackNeutronicsState(y_n, params.N, phi_1, phi_2, C);

        std::vector<double> phi(static_cast<std::size_t>(params.N), 0.0);
        for (int idx = 0; idx < params.N; ++idx) {
            phi[static_cast<std::size_t>(idx)] =
                phi_1[static_cast<std::size_t>(idx)] + phi_2[static_cast<std::size_t>(idx)];
        }

        const double Ts_core_0 = (params.core_inlet_mode == "hx_coupled")
            ? msr::TransportDelay(Ts_HX1_0, params.tau_hx_c, params.Ts_in, buffer_hx_c, step, params.outer_dt)
            : params.Ts_in;
        y_th = msr::SolveThermalHydraulics(params, y_th, q_prime, Ts_core_0);
        temperature_fuel.assign(y_th.begin(), y_th.begin() + params.N);
        temperature_graphite.assign(y_th.begin() + params.N, y_th.begin() + 2 * params.N);
        const double Ts_core_L = temperature_fuel.back();

        const double Ts_HX1_L =
            msr::TransportDelay(Ts_core_L, params.tau_c_hx, params.Ts_out, buffer_c_hx, step, params.outer_dt);
        const double Tss_HX1_0 =
            msr::TransportDelay(Tss_HX2_0, params.tau_r_hx, params.Tss_in, buffer_r_hx, step, params.outer_dt);
        y_hx1 = msr::SolveHeatExchanger(params, y_hx1, Ts_HX1_L, Tss_HX1_0, msr::Hx1Config(params));
        const double new_Ts_HX1_0 = y_hx1.front();
        const double Tss_HX1_L = y_hx1[static_cast<std::size_t>(2 * params.Nx - 1)];

        const double Tss_HX2_L =
            msr::TransportDelay(Tss_HX1_L, params.tau_hx_r, params.Tss_out, buffer_hx_r, step, params.outer_dt);
        const double Tsss_HX2_0 =
            msr::TransportDelay(Tsss_pp_0, params.tau_pp_r, params.Tsss_in, buffer_pp_r, step, params.outer_dt);
        y_hx2 = msr::SolveHeatExchanger(params, y_hx2, Tss_HX2_L, Tsss_HX2_0, msr::Hx2Config(params));
        const double new_Tss_HX2_0 = y_hx2.front();
        const double Tsss_HX2_L = y_hx2[static_cast<std::size_t>(2 * params.Nx - 1)];

        const double Tsss_pp_L =
            msr::TransportDelay(Tsss_HX2_L, params.tau_r_pp, params.Tsss_out, buffer_r_pp, step, params.outer_dt);
        params.brayton_available_heat_W = msr::Trapz(q_prime, params.z);
        const double new_Tsss_pp_0 = msr::PowerPlantTemp(Tsss_pp_L, params, step);

        Ts_HX1_0 = new_Ts_HX1_0;
        Tss_HX2_0 = new_Tss_HX2_0;
        Tsss_pp_0 = new_Tsss_pp_0;

        final_diag.phi_mid = phi[static_cast<std::size_t>(mid_idx)];
        final_diag.rho = external_reactivity;
        final_diag.power = msr::Trapz(q_prime, params.z);
        final_diag.fuel_mid = temperature_fuel[static_cast<std::size_t>(mid_idx)];
        final_diag.graphite_mid = temperature_graphite[static_cast<std::size_t>(mid_idx)];
        final_diag.core_inlet = Ts_core_0;
        final_diag.core_outlet = Ts_core_L;
        final_diag.hx1_hot_outlet = Ts_HX1_0;
        final_diag.hx1_cold_outlet = Tss_HX1_L;
        final_diag.hx2_hot_outlet = Tss_HX2_0;
        final_diag.hx2_cold_outlet = Tsss_HX2_L;
        final_diag.brayton_return = Tsss_pp_0;
    }

    ScenarioResult result;
    store_state_to_kernel(params, y_n, y_th, y_hx1, y_hx2, Ts_HX1_0, Tss_HX2_0, Tsss_pp_0, result.final_state);
    result.final_diag = final_diag;
    return result;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 9 && argc != 10 && argc != 12) {
        std::cerr << "usage: " << argv[0]
                  << " <states.bin> <delays.bin> <params.bin> <rod_positions.bin> <external_reactivities.bin>"
                  << " <step_count> <scenario_count> <repeats> [warmup] [state_out.bin diag_out.bin]\n";
        return 2;
    }

    const std::string states_path = argv[1];
    const std::string delays_path = argv[2];
    const std::string params_path = argv[3];
    const std::string rod_positions_path = argv[4];
    const std::string external_reactivities_path = argv[5];
    const int step_count = std::atoi(argv[6]);
    const int scenario_count = std::atoi(argv[7]);
    const int repeats = std::atoi(argv[8]);
    const int warmup = (argc == 9 || argc == 12) ? 0 : std::atoi(argv[9]);
    const bool write_outputs = (argc == 12);
    const std::string state_out_path = write_outputs ? argv[10] : std::string();
    const std::string diag_out_path = write_outputs ? argv[11] : std::string();

    if (step_count <= 0 || scenario_count <= 0 || repeats <= 0 || warmup < 0) {
        throw std::runtime_error("step_count, scenario_count, repeats must be > 0 and warmup >= 0");
    }

    const std::size_t scenario_count_u = static_cast<std::size_t>(scenario_count);
    const std::size_t control_count = static_cast<std::size_t>(step_count) * scenario_count_u;

    const auto base_states = read_blob_array<msr_vitis::StepState>(states_path, scenario_count_u);
    const auto base_delays = read_blob_array<msr_vitis::DelayBundle>(delays_path, scenario_count_u);
    const auto base_params = read_blob_array<msr_vitis::KernelParams>(params_path, scenario_count_u);
    const auto rod_positions = read_scalar_array<double>(rod_positions_path, control_count);
    const auto external_reactivities = read_scalar_array<double>(external_reactivities_path, control_count);

    TimingStats total_stats{};
    std::vector<msr_vitis::StepState> last_states;
    std::vector<msr_vitis::StepDiagnostics> last_diags;
    volatile double checksum = 0.0;

    for (int iter = 0; iter < warmup + repeats; ++iter) {
        std::vector<msr_vitis::StepState> final_states(scenario_count_u);
        std::vector<msr_vitis::StepDiagnostics> final_diags(scenario_count_u);

        const auto start = std::chrono::steady_clock::now();
        for (std::size_t scenario = 0; scenario < scenario_count_u; ++scenario) {
            const std::size_t control_base = scenario * static_cast<std::size_t>(step_count);
            const auto result = run_plain_scenario(
                base_states[scenario],
                base_delays[scenario],
                base_params[scenario],
                rod_positions.data() + control_base,
                external_reactivities.data() + control_base,
                step_count
            );
            final_states[scenario] = result.final_state;
            final_diags[scenario] = result.final_diag;
        }
        const auto end = std::chrono::steady_clock::now();
        const double total_us = std::chrono::duration<double, std::micro>(end - start).count();

        for (std::size_t scenario = 0; scenario < scenario_count_u; ++scenario) {
            checksum += final_diags[scenario].power + final_diags[scenario].brayton_return;
        }

        if (iter >= warmup) {
            update_stats(total_stats, total_us);
            last_states = std::move(final_states);
            last_diags = std::move(final_diags);
        }
    }

    if (write_outputs) {
        write_blob_array(state_out_path, last_states);
        write_blob_array(diag_out_path, last_diags);
    }

    const double total_avg_us = avg_us(total_stats, repeats);
    const double per_step_avg_us = total_avg_us / static_cast<double>(step_count * scenario_count);

    std::cout << std::setprecision(17);
    std::cout << "timing.repeats=" << repeats << "\n";
    std::cout << "timing.warmup=" << warmup << "\n";
    std::cout << "timing.total.min_us=" << total_stats.min_us << "\n";
    std::cout << "timing.total.max_us=" << total_stats.max_us << "\n";
    std::cout << "timing.total.avg_us=" << total_avg_us << "\n";
    std::cout << "timing.per_step.avg_us=" << per_step_avg_us << "\n";
    std::cout << "timing.step_count=" << step_count << "\n";
    std::cout << "timing.scenario_count=" << scenario_count << "\n";
    if (!last_diags.empty()) {
        const auto& diag0 = last_diags.front();
        std::cout << "scenario0.phi_mid=" << diag0.phi_mid << "\n";
        std::cout << "scenario0.rho=" << diag0.rho << "\n";
        std::cout << "scenario0.power=" << diag0.power << "\n";
        std::cout << "scenario0.fuel_mid=" << diag0.fuel_mid << "\n";
        std::cout << "scenario0.graphite_mid=" << diag0.graphite_mid << "\n";
        std::cout << "scenario0.core_inlet=" << diag0.core_inlet << "\n";
        std::cout << "scenario0.core_outlet=" << diag0.core_outlet << "\n";
        std::cout << "scenario0.hx1_hot_outlet=" << diag0.hx1_hot_outlet << "\n";
        std::cout << "scenario0.hx1_cold_outlet=" << diag0.hx1_cold_outlet << "\n";
        std::cout << "scenario0.hx2_hot_outlet=" << diag0.hx2_hot_outlet << "\n";
        std::cout << "scenario0.hx2_cold_outlet=" << diag0.hx2_cold_outlet << "\n";
        std::cout << "scenario0.brayton_return=" << diag0.brayton_return << "\n";
    }
    std::cout << "timing.checksum=" << checksum << "\n";
    return 0;
}
