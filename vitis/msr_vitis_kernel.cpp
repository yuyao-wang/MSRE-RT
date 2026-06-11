#include <math.h>

namespace msr_vitis {

#ifndef MSR_CROSS_SECTION_LANE_FACTOR
#define MSR_CROSS_SECTION_LANE_FACTOR 4
#endif

#ifndef MSR_NEUTRONICS_LANE_FACTOR
#define MSR_NEUTRONICS_LANE_FACTOR 4
#endif

#ifndef MSR_THERMAL_LANE_FACTOR
#define MSR_THERMAL_LANE_FACTOR 4
#endif

#ifndef MSR_HEAT_EXCHANGER_LANE_FACTOR
#define MSR_HEAT_EXCHANGER_LANE_FACTOR 4
#endif

constexpr int kEnergyGroups = 2;
constexpr int kPrecursorGroups = 6;
constexpr int kMaxN = 128;
constexpr int kMaxDelaySlots = 32;
constexpr int kMaxLoopHistory = 64;
constexpr int kCrossSectionLaneFactor = MSR_CROSS_SECTION_LANE_FACTOR;
constexpr int kNeutronicsLaneFactor = MSR_NEUTRONICS_LANE_FACTOR;
constexpr int kThermalLaneFactor = MSR_THERMAL_LANE_FACTOR;
constexpr int kHeatExchangerLaneFactor = MSR_HEAT_EXCHANGER_LANE_FACTOR;
constexpr int kReductionAccumulatorSlots = 8;

enum InletMode : int {
    kInletRecirculate = 0,
    kInletFresh = 1,
    kInletCopy = 2,
};

enum CoreInletMode : int {
    kCoreInletPrescribed = 0,
    kCoreInletHxCoupled = 1,
};

struct DelayLine {
    double data[kMaxDelaySlots];
    int head;
    int size;
    int delay_steps;
};

struct DelayBundle {
    DelayLine hx_c;
    DelayLine c_hx;
    DelayLine r_hx;
    DelayLine hx_r;
    DelayLine r_pp;
    DelayLine pp_r;
};

struct PrecursorHistory {
    double outlet_history[kPrecursorGroups][kMaxLoopHistory];
    double last_outlet[kPrecursorGroups];
    int write_index;
    int valid_count;
};

struct StepState {
    double phi1[kMaxN];
    double phi2[kMaxN];
    double C[kPrecursorGroups][kMaxN];
    double fuel[kMaxN];
    double graphite[kMaxN];
    double hx1_hot[kMaxN];
    double hx1_cold[kMaxN];
    double hx2_hot[kMaxN];
    double hx2_cold[kMaxN];
    double Ts_HX1_0;
    double Tss_HX2_0;
    double Tsss_pp_0;
    PrecursorHistory precursor_history;
};

struct CrossSections {
    double D[kEnergyGroups][kMaxN];
    double sigma_a[kEnergyGroups][kMaxN];
    double sigma_s12[kMaxN];
    double nu_sigma_f[kEnergyGroups][kMaxN];
    double sigma_f[kEnergyGroups][kMaxN];
    double sigma_r[kEnergyGroups][kMaxN];
};

struct KernelParams {
    int N;
    int Nx;
    int hardware_substeps;
    int inlet_mode;
    int core_inlet_mode;
    int use_graphite_axial_conduction;

    int precursor_delay_older;
    int precursor_delay_newer;
    double precursor_interp_newer;

    double dz;
    double outer_dt;
    double u_core;
    double u_precursor;
    double power_scale;
    double Beta;

    double beta[kPrecursorGroups];
    double lambda_i[kPrecursorGroups];
    double neutron_velocity[kEnergyGroups];
    double nu[kEnergyGroups];
    double chi_p[kEnergyGroups];
    double chi_d[kEnergyGroups];
    double d_e[kEnergyGroups];

    double D_ref[kEnergyGroups][kMaxN];
    double sigma_a_ref[kEnergyGroups][kMaxN];
    double sigma_s12_ref[kMaxN];
    double nu_sigma_f_ref[kEnergyGroups][kMaxN];
    double transverse_buckling_sq[kEnergyGroups][kMaxN];

    double a_sigma_a_s[kEnergyGroups][kMaxN];
    double a_sigma_a_gr[kEnergyGroups][kMaxN];
    double a_sigma_s12_s[kMaxN];
    double a_sigma_s12_gr[kMaxN];
    double a_nu_sigma_f_s[kEnergyGroups][kMaxN];
    double a_nu_sigma_f_gr[kEnergyGroups][kMaxN];
    double a_D_s[kEnergyGroups][kMaxN];
    double a_D_gr[kEnergyGroups][kMaxN];
    double rod_shape[kEnergyGroups][kMaxN];
    double rod_sigma_a_amplitude[kEnergyGroups];
    double external_reactivity_to_absorption[kEnergyGroups];

    double T_s_ref[kMaxN];
    double T_gr_ref[kMaxN];
    double phi1_ref[kMaxN];
    double phi2_ref[kMaxN];
    double A_f[kMaxN];
    double z[kMaxN];

    double min_diffusion;
    double min_cross_section;
    double reference_multiplication_ratio;
    double precursor_loop_efficiency;
    double precursor_loop_tau;

    double rho_s;
    double c_p_s;
    double A_s;
    double rho_gr;
    double c_p_g;
    double A_gr;
    double h_sgr;
    double P_sgr;
    double k_gr;
    double eta_s;
    double eta_gr;
    double err;
    double bc_s0;

    double hx1_dx;
    double hx1_hot_velocity;
    double hx1_cold_velocity;
    double hx1_hot_exchange_coeff;
    double hx1_cold_exchange_coeff;

    double hx2_dx;
    double hx2_hot_velocity;
    double hx2_cold_velocity;
    double hx2_hot_exchange_coeff;
    double hx2_cold_exchange_coeff;

    double Ts_in;
    double Ts_out;
    double Tss_in;
    double Tss_out;
    double Tsss_in;
    double Tsss_out;

    double brayton_gamma;
    double brayton_eta_c;
    double brayton_eta_t;
    double brayton_pi_c;
    double brayton_pi_t;
    double brayton_recuperator_efficiency;
    double brayton_cooler_outlet_temp;
    double brayton_min_heater_approach;
    double brayton_mdot;
    double c_p_sss;
};

struct StepDiagnostics {
    double phi_mid;
    double rho;
    double power;
    double fuel_mid;
    double graphite_mid;
    double core_inlet;
    double core_outlet;
    double hx1_hot_outlet;
    double hx1_cold_outlet;
    double hx2_hot_outlet;
    double hx2_cold_outlet;
    double brayton_return;
};

inline double clip_min(double value, double lower) {
    return value < lower ? lower : value;
}

inline double max2(double a, double b) {
    return a > b ? a : b;
}

inline double reduce_sum_tree_8(const double values[kReductionAccumulatorSlots]) {
#pragma HLS INLINE
    const double level0_0 = values[0] + values[1];
    const double level0_1 = values[2] + values[3];
    const double level0_2 = values[4] + values[5];
    const double level0_3 = values[6] + values[7];
    const double level1_0 = level0_0 + level0_1;
    const double level1_1 = level0_2 + level0_3;
    return level1_0 + level1_1;
}

inline int wrap_index(int idx, int size) {
    while (idx < 0) {
        idx += size;
    }
    while (idx >= size) {
        idx -= size;
    }
    return idx;
}

double trapz_uniform(const double* y, const double* x, int N) {
    double partial[kReductionAccumulatorSlots];
#pragma HLS ARRAY_PARTITION variable=partial complete dim=1

    for (int lane = 0; lane < kReductionAccumulatorSlots; ++lane) {
#pragma HLS UNROLL
        partial[lane] = 0.0;
    }

    if (N <= 1) {
        return 0.0;
    }

    double prev_y = y[0];
    double prev_x = x[0];
    for (int idx = 1; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
        const double curr_y = y[idx];
        const double curr_x = x[idx];
        const double term = 0.5 * (prev_y + curr_y) * (curr_x - prev_x);
        const int slot = (idx - 1) & (kReductionAccumulatorSlots - 1);
        partial[slot] += term;
        prev_y = curr_y;
        prev_x = curr_x;
    }
    return reduce_sum_tree_8(partial);
}

double delay_line_update(DelayLine& line, double input_value, double initial_output, int step) {
    if (step < line.delay_steps) {
        const int tail = wrap_index(line.head + line.size, kMaxDelaySlots);
        line.data[tail] = input_value;
        if (line.size < kMaxDelaySlots) {
            ++line.size;
        } else {
            line.head = wrap_index(line.head + 1, kMaxDelaySlots);
        }
        return initial_output;
    }

    const double output_value = (line.size > 0) ? line.data[line.head] : initial_output;
    if (line.size > 0) {
        line.head = wrap_index(line.head + 1, kMaxDelaySlots);
        --line.size;
    }
    const int tail = wrap_index(line.head + line.size, kMaxDelaySlots);
    line.data[tail] = input_value;
    if (line.size < kMaxDelaySlots) {
        ++line.size;
    }
    return output_value;
}

double sample_precursor_history(const PrecursorHistory& history, int group, int steps_old) {
    if (history.valid_count <= 0) {
        return history.last_outlet[group];
    }
    const int available = history.valid_count - 1;
    const int bounded_steps = steps_old > available ? available : steps_old;
    const int latest_index = wrap_index(history.write_index - 1, kMaxLoopHistory);
    const int sample_index = wrap_index(latest_index - bounded_steps, kMaxLoopHistory);
    return history.outlet_history[group][sample_index];
}

void record_precursor_history(PrecursorHistory& history, const double outlet[kPrecursorGroups]) {
#pragma HLS INLINE
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        history.outlet_history[group][history.write_index] = outlet[group];
        history.last_outlet[group] = outlet[group];
    }
    history.write_index = wrap_index(history.write_index + 1, kMaxLoopHistory);
    if (history.valid_count < kMaxLoopHistory) {
        ++history.valid_count;
    }
}

void precursor_inlet_from_loop(
    const KernelParams& params,
    const PrecursorHistory& history,
    double inlet[kPrecursorGroups]
) {
#pragma HLS INLINE
    if (params.inlet_mode == kInletFresh) {
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            inlet[group] = 0.0;
        }
        return;
    }

    if (params.inlet_mode == kInletCopy) {
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            inlet[group] = history.last_outlet[group];
        }
        return;
    }

    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        const double older = sample_precursor_history(history, group, params.precursor_delay_older);
        const double newer = sample_precursor_history(history, group, params.precursor_delay_newer);
        const double delayed =
            (1.0 - params.precursor_interp_newer) * older +
            params.precursor_interp_newer * newer;
        inlet[group] =
            params.precursor_loop_efficiency *
            delayed *
            exp(-params.lambda_i[group] * params.precursor_loop_tau);
    }
}

void cross_sections_kernel(
    const KernelParams& params,
    const StepState& state,
    double rod_position,
    double external_reactivity,
    CrossSections& xs
) {
    for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kCrossSectionLaneFactor
        const double delta_T_s = state.fuel[idx] - params.T_s_ref[idx];
        const double delta_T_gr = state.graphite[idx] - params.T_gr_ref[idx];
        xs.sigma_s12[idx] = clip_min(
            params.sigma_s12_ref[idx] +
                params.a_sigma_s12_s[idx] * delta_T_s +
                params.a_sigma_s12_gr[idx] * delta_T_gr,
            0.0
        );

        for (int group = 0; group < kEnergyGroups; ++group) {
#pragma HLS UNROLL
            double delta_sigma_a =
                rod_position * params.rod_shape[group][idx] * params.rod_sigma_a_amplitude[group];
            if (external_reactivity != 0.0) {
                delta_sigma_a +=
                    (-external_reactivity) *
                    params.rod_shape[group][idx] *
                    params.external_reactivity_to_absorption[group];
            }

            xs.D[group][idx] = clip_min(
                params.D_ref[group][idx] +
                    params.a_D_s[group][idx] * delta_T_s +
                    params.a_D_gr[group][idx] * delta_T_gr,
                params.min_diffusion
            );
            xs.sigma_a[group][idx] = clip_min(
                params.sigma_a_ref[group][idx] +
                    params.a_sigma_a_s[group][idx] * delta_T_s +
                    params.a_sigma_a_gr[group][idx] * delta_T_gr +
                    delta_sigma_a,
                params.min_cross_section
            );
            xs.nu_sigma_f[group][idx] = clip_min(
                params.nu_sigma_f_ref[group][idx] +
                    params.a_nu_sigma_f_s[group][idx] * delta_T_s +
                    params.a_nu_sigma_f_gr[group][idx] * delta_T_gr,
                params.min_cross_section
            );
            xs.sigma_f[group][idx] = xs.nu_sigma_f[group][idx] / params.nu[group];
            xs.sigma_r[group][idx] =
                xs.sigma_a[group][idx] +
                xs.D[group][idx] * params.transverse_buckling_sq[group][idx];
        }
        xs.sigma_r[0][idx] += xs.sigma_s12[idx];
    }
}

double estimate_global_rho(const KernelParams& params, const CrossSections& xs) {
    double production[kMaxN];
    double absorption[kMaxN];

#pragma HLS ARRAY_PARTITION variable=production cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=absorption cyclic factor=kCrossSectionLaneFactor dim=1

    for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kCrossSectionLaneFactor
        production[idx] =
            xs.nu_sigma_f[0][idx] * params.phi1_ref[idx] +
            xs.nu_sigma_f[1][idx] * params.phi2_ref[idx];
        absorption[idx] =
            xs.sigma_a[0][idx] * params.phi1_ref[idx] +
            xs.sigma_a[1][idx] * params.phi2_ref[idx];
    }

    const double ratio =
        trapz_uniform(production, params.z, params.N) /
        max2(trapz_uniform(absorption, params.z, params.N), 1.0e-12);
    const double k_ratio = ratio / max2(params.reference_multiplication_ratio, 1.0e-12);
    return (k_ratio - 1.0) / max2(k_ratio, 1.0e-12);
}

void diffusion_term(
    const double phi[kMaxN],
    const double diffusion[kMaxN],
    int N,
    double dz,
    double d_extrap,
    double result[kMaxN]
) {
    const double left_ghost = phi[1] - 2.0 * dz * phi[0] / max2(d_extrap, 1.0e-12);
    const double right_ghost = phi[N - 2] - 2.0 * dz * phi[N - 1] / max2(d_extrap, 1.0e-12);

#pragma HLS ARRAY_PARTITION variable=phi cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=diffusion cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=result cyclic factor=kNeutronicsLaneFactor dim=1

    for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
        const double phi_center = phi[idx];
        const double phi_left = (idx == 0) ? left_ghost : phi[idx - 1];
        const double phi_right = (idx + 1 == N) ? right_ghost : phi[idx + 1];
        const double d_left = (idx == 0) ? diffusion[0] : 0.5 * (diffusion[idx - 1] + diffusion[idx]);
        const double d_right = (idx + 1 == N) ? diffusion[N - 1] : 0.5 * (diffusion[idx] + diffusion[idx + 1]);
        result[idx] = (d_right * (phi_right - phi_center) - d_left * (phi_center - phi_left)) / (dz * dz);
    }
}

void neutronics_rhs(
    const KernelParams& params,
    const CrossSections& xs,
    const double precursor_inlet[kPrecursorGroups],
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    const double C[kPrecursorGroups][kMaxN],
    double dphi1[kMaxN],
    double dphi2[kMaxN],
    double dC[kPrecursorGroups][kMaxN]
) {
    double F[kMaxN];
    double delayed_source[kMaxN];
    double diffusion_1[kMaxN];
    double diffusion_2[kMaxN];

#pragma HLS ARRAY_PARTITION variable=precursor_inlet complete
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=dC complete dim=1
#pragma HLS ARRAY_PARTITION variable=dC cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dphi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dphi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=F cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=delayed_source cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=diffusion_1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=diffusion_2 cyclic factor=kNeutronicsLaneFactor dim=1
    diffusion_term(phi1, xs.D[0], params.N, params.dz, params.d_e[0], diffusion_1);
    diffusion_term(phi2, xs.D[1], params.N, params.dz, params.d_e[1], diffusion_2);

    for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
        F[idx] = xs.nu_sigma_f[0][idx] * phi1[idx] + xs.nu_sigma_f[1][idx] * phi2[idx];
        delayed_source[idx] = 0.0;
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            delayed_source[idx] += params.lambda_i[group] * C[group][idx];
        }

        const double rhs_1 =
            diffusion_1[idx] -
            xs.sigma_r[0][idx] * phi1[idx] +
            params.chi_p[0] * (1.0 - params.Beta) * F[idx] +
            params.chi_d[0] * delayed_source[idx];

        const double rhs_2 =
            diffusion_2[idx] -
            xs.sigma_r[1][idx] * phi2[idx] +
            xs.sigma_s12[idx] * phi1[idx] +
            params.chi_p[1] * (1.0 - params.Beta) * F[idx] +
            params.chi_d[1] * delayed_source[idx];

        dphi1[idx] = params.neutron_velocity[0] * rhs_1;
        dphi2[idx] = params.neutron_velocity[1] * rhs_2;
    }

    for (int group = 0; group < kPrecursorGroups; ++group) {
        for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
            const double C_im1 = (idx == 0) ? precursor_inlet[group] : C[group][idx - 1];
            const double precursor_advection = params.u_precursor * (C[group][idx] - C_im1) / params.dz;
            dC[group][idx] =
                params.beta[group] * F[idx] -
                params.lambda_i[group] * C[group][idx] -
                precursor_advection;
        }
    }
}

void compute_q_prime(
    const KernelParams& params,
    const CrossSections& xs,
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    double q_prime[kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=q_prime cyclic factor=kNeutronicsLaneFactor dim=1
    for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
        const double q_vol =
            params.power_scale *
            (xs.sigma_f[0][idx] * phi1[idx] + xs.sigma_f[1][idx] * phi2[idx]);
        q_prime[idx] = params.A_f[idx] * q_vol;
    }
}

void combine_neutronics(
    int N,
    double dt,
    double phi1[kMaxN],
    double phi2[kMaxN],
    double C[kPrecursorGroups][kMaxN],
    const double k1_phi1[kMaxN],
    const double k1_phi2[kMaxN],
    const double k1_C[kPrecursorGroups][kMaxN],
    const double k2_phi1[kMaxN],
    const double k2_phi2[kMaxN],
    const double k2_C[kPrecursorGroups][kMaxN],
    const double k3_phi1[kMaxN],
    const double k3_phi2[kMaxN],
    const double k3_C[kPrecursorGroups][kMaxN],
    const double k4_phi1[kMaxN],
    const double k4_phi2[kMaxN],
    const double k4_C[kPrecursorGroups][kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
    for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
        phi1[idx] += (dt / 6.0) * (k1_phi1[idx] + 2.0 * k2_phi1[idx] + 2.0 * k3_phi1[idx] + k4_phi1[idx]);
        phi2[idx] += (dt / 6.0) * (k1_phi2[idx] + 2.0 * k2_phi2[idx] + 2.0 * k3_phi2[idx] + k4_phi2[idx]);
    }
    for (int group = 0; group < kPrecursorGroups; ++group) {
        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
            C[group][idx] +=
                (dt / 6.0) *
                (k1_C[group][idx] + 2.0 * k2_C[group][idx] + 2.0 * k3_C[group][idx] + k4_C[group][idx]);
        }
    }
}

void load_neutronics_stage(
    int N,
    double scale,
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    const double C[kPrecursorGroups][kMaxN],
    const double dphi1[kMaxN],
    const double dphi2[kMaxN],
    const double dC[kPrecursorGroups][kMaxN],
    double phi1_stage[kMaxN],
    double phi2_stage[kMaxN],
    double C_stage[kPrecursorGroups][kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=phi1_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=dC complete dim=1
#pragma HLS ARRAY_PARTITION variable=dC cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=C_stage complete dim=1
#pragma HLS ARRAY_PARTITION variable=C_stage cyclic factor=kNeutronicsLaneFactor dim=2
    for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
        phi1_stage[idx] = phi1[idx] + scale * dphi1[idx];
        phi2_stage[idx] = phi2[idx] + scale * dphi2[idx];
    }
    for (int group = 0; group < kPrecursorGroups; ++group) {
        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
            C_stage[group][idx] = C[group][idx] + scale * dC[group][idx];
        }
    }
}

void neutronics_kernel(
    const KernelParams& params,
    CrossSections& xs,
    StepState& state,
    double q_prime[kMaxN]
) {
    double precursor_inlet[kPrecursorGroups];
#pragma HLS ARRAY_PARTITION variable=precursor_inlet complete
    precursor_inlet_from_loop(params, state.precursor_history, precursor_inlet);

    const double dt = params.outer_dt / static_cast<double>(params.hardware_substeps);
    for (int substep = 0; substep < params.hardware_substeps; ++substep) {
        double k1_phi1[kMaxN], k2_phi1[kMaxN], k3_phi1[kMaxN], k4_phi1[kMaxN];
        double k1_phi2[kMaxN], k2_phi2[kMaxN], k3_phi2[kMaxN], k4_phi2[kMaxN];
        double k1_C[kPrecursorGroups][kMaxN];
        double k2_C[kPrecursorGroups][kMaxN];
        double k3_C[kPrecursorGroups][kMaxN];
        double k4_C[kPrecursorGroups][kMaxN];
        double phi1_stage[kMaxN], phi2_stage[kMaxN];
        double C_stage[kPrecursorGroups][kMaxN];

#pragma HLS ARRAY_PARTITION variable=k1_phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k1_phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi1_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k1_C complete dim=1
#pragma HLS ARRAY_PARTITION variable=k1_C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=k2_C complete dim=1
#pragma HLS ARRAY_PARTITION variable=k2_C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=k3_C complete dim=1
#pragma HLS ARRAY_PARTITION variable=k3_C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=k4_C complete dim=1
#pragma HLS ARRAY_PARTITION variable=k4_C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=C_stage complete dim=1
#pragma HLS ARRAY_PARTITION variable=C_stage cyclic factor=kNeutronicsLaneFactor dim=2

        neutronics_rhs(params, xs, precursor_inlet, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C);
        load_neutronics_stage(params.N, 0.5 * dt, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k2_phi1, k2_phi2, k2_C);
        load_neutronics_stage(params.N, 0.5 * dt, state.phi1, state.phi2, state.C, k2_phi1, k2_phi2, k2_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k3_phi1, k3_phi2, k3_C);
        load_neutronics_stage(params.N, dt, state.phi1, state.phi2, state.C, k3_phi1, k3_phi2, k3_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k4_phi1, k4_phi2, k4_C);
        combine_neutronics(params.N, dt, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C, k2_phi1, k2_phi2, k2_C, k3_phi1, k3_phi2, k3_C, k4_phi1, k4_phi2, k4_C);
    }

    compute_q_prime(params, xs, state.phi1, state.phi2, q_prime);

    double outlet[kPrecursorGroups];
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        outlet[group] = state.C[group][params.N - 1];
    }
    record_precursor_history(state.precursor_history, outlet);
}

void thermal_rhs(
    const KernelParams& params,
    const double q_prime[kMaxN],
    double inlet_temperature,
    const double fuel[kMaxN],
    const double graphite[kMaxN],
    double dfuel[kMaxN],
    double dgraphite[kMaxN]
) {
    const double salt_capacity = params.rho_s * params.c_p_s * params.A_s;
    const double graphite_capacity = params.rho_gr * params.c_p_g * params.A_gr;
    const double heat_exchange = params.h_sgr * params.P_sgr;
    const double graphite_axial_conductivity = params.k_gr * params.A_gr;

#pragma HLS ARRAY_PARTITION variable=q_prime cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dfuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dgraphite cyclic factor=kThermalLaneFactor dim=1
    for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
        const double fuel_im1 = (idx == 0) ? inlet_temperature : fuel[idx - 1];
        const double fuel_gradient = (fuel[idx] - fuel_im1) / params.dz;
        const double fuel_exchange = heat_exchange * (graphite[idx] - fuel[idx]);
        dfuel[idx] =
            -params.u_core * fuel_gradient +
            (params.eta_s * q_prime[idx] + fuel_exchange) / salt_capacity +
            params.err;

        double graphite_rhs =
            (params.eta_gr * q_prime[idx] - fuel_exchange) / graphite_capacity +
            params.err;
        if (params.use_graphite_axial_conduction != 0) {
            const double graphite_left = (idx == 0) ? graphite[1] : graphite[idx - 1];
            const double graphite_right = (idx + 1 == params.N) ? graphite[params.N - 2] : graphite[idx + 1];
            const double second_derivative =
                (idx == 0 || idx + 1 == params.N)
                    ? 2.0 * ((idx == 0 ? graphite_right : graphite_left) - graphite[idx]) / (params.dz * params.dz)
                    : (graphite_right - 2.0 * graphite[idx] + graphite_left) / (params.dz * params.dz);
            graphite_rhs += (graphite_axial_conductivity / graphite_capacity) * second_derivative;
        }
        dgraphite[idx] = graphite_rhs;
    }
    dfuel[0] = inlet_temperature - fuel[0];
}

void load_thermal_stage(
    int N,
    double scale,
    const double fuel[kMaxN],
    const double graphite[kMaxN],
    const double dfuel[kMaxN],
    const double dgraphite[kMaxN],
    double fuel_stage[kMaxN],
    double graphite_stage[kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dfuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dgraphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=fuel_stage cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite_stage cyclic factor=kThermalLaneFactor dim=1
    for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
        fuel_stage[idx] = fuel[idx] + scale * dfuel[idx];
        graphite_stage[idx] = graphite[idx] + scale * dgraphite[idx];
    }
}

void thermal_kernel(
    const KernelParams& params,
    const double q_prime[kMaxN],
    double Ts_core_inlet,
    StepState& state
) {
    const double dt = params.outer_dt / static_cast<double>(params.hardware_substeps);
    for (int substep = 0; substep < params.hardware_substeps; ++substep) {
        double k1_fuel[kMaxN], k2_fuel[kMaxN], k3_fuel[kMaxN], k4_fuel[kMaxN];
        double k1_graphite[kMaxN], k2_graphite[kMaxN], k3_graphite[kMaxN], k4_graphite[kMaxN];
        double fuel_stage[kMaxN], graphite_stage[kMaxN];

#pragma HLS ARRAY_PARTITION variable=k1_fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k1_graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=fuel_stage cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite_stage cyclic factor=kThermalLaneFactor dim=1
        thermal_rhs(params, q_prime, Ts_core_inlet, state.fuel, state.graphite, k1_fuel, k1_graphite);
        load_thermal_stage(params.N, 0.5 * dt, state.fuel, state.graphite, k1_fuel, k1_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k2_fuel, k2_graphite);
        load_thermal_stage(params.N, 0.5 * dt, state.fuel, state.graphite, k2_fuel, k2_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k3_fuel, k3_graphite);
        load_thermal_stage(params.N, dt, state.fuel, state.graphite, k3_fuel, k3_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k4_fuel, k4_graphite);

        for (int idx = 0; idx < params.N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
            state.fuel[idx] += (dt / 6.0) * (k1_fuel[idx] + 2.0 * k2_fuel[idx] + 2.0 * k3_fuel[idx] + k4_fuel[idx]);
            state.graphite[idx] += (dt / 6.0) * (k1_graphite[idx] + 2.0 * k2_graphite[idx] + 2.0 * k3_graphite[idx] + k4_graphite[idx]);
        }
        state.fuel[0] = Ts_core_inlet;
    }
}

void hx_rhs(
    int N,
    double dx,
    double hot_velocity,
    double cold_velocity,
    double hot_exchange_coeff,
    double cold_exchange_coeff,
    double err,
    double hot_inlet,
    double cold_inlet,
    const double hot[kMaxN],
    const double cold[kMaxN],
    double dhot[kMaxN],
    double dcold[kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dhot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dcold cyclic factor=kHeatExchangerLaneFactor dim=1
    for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
        const double hot_gradient = (hot_velocity >= 0.0)
            ? ((idx == 0) ? (hot[idx] - hot_inlet) / dx : (hot[idx] - hot[idx - 1]) / dx)
            : ((idx + 1 == N) ? (hot_inlet - hot[idx]) / dx : (hot[idx + 1] - hot[idx]) / dx);
        const double cold_gradient = (cold_velocity >= 0.0)
            ? ((idx == 0) ? (cold[idx] - cold_inlet) / dx : (cold[idx] - cold[idx - 1]) / dx)
            : ((idx + 1 == N) ? (cold_inlet - cold[idx]) / dx : (cold[idx + 1] - cold[idx]) / dx);
        const double delta_t = hot[idx] - cold[idx];
        dhot[idx] = -hot_velocity * hot_gradient - hot_exchange_coeff * delta_t + err;
        dcold[idx] = -cold_velocity * cold_gradient + cold_exchange_coeff * delta_t + err;
    }
}

void hx_kernel(
    int N,
    int hardware_substeps,
    double outer_dt,
    double dx,
    double hot_velocity,
    double cold_velocity,
    double hot_exchange_coeff,
    double cold_exchange_coeff,
    double err,
    double hot_inlet,
    double cold_inlet,
    double hot[kMaxN],
    double cold[kMaxN]
) {
    const double dt = outer_dt / static_cast<double>(hardware_substeps);
    for (int substep = 0; substep < hardware_substeps; ++substep) {
        double k1_hot[kMaxN], k2_hot[kMaxN], k3_hot[kMaxN], k4_hot[kMaxN];
        double k1_cold[kMaxN], k2_cold[kMaxN], k3_cold[kMaxN], k4_cold[kMaxN];
        double hot_stage[kMaxN], cold_stage[kMaxN];

#pragma HLS ARRAY_PARTITION variable=k1_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k1_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k2_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k3_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=k4_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=hot_stage cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=cold_stage cyclic factor=kHeatExchangerLaneFactor dim=1
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot, cold, k1_hot, k1_cold);
        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
            hot_stage[idx] = hot[idx] + 0.5 * dt * k1_hot[idx];
            cold_stage[idx] = cold[idx] + 0.5 * dt * k1_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k2_hot, k2_cold);
        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
            hot_stage[idx] = hot[idx] + 0.5 * dt * k2_hot[idx];
            cold_stage[idx] = cold[idx] + 0.5 * dt * k2_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k3_hot, k3_cold);
        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
            hot_stage[idx] = hot[idx] + dt * k3_hot[idx];
            cold_stage[idx] = cold[idx] + dt * k3_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k4_hot, k4_cold);

        for (int idx = 0; idx < N; ++idx) {
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
            hot[idx] += (dt / 6.0) * (k1_hot[idx] + 2.0 * k2_hot[idx] + 2.0 * k3_hot[idx] + k4_hot[idx]);
            cold[idx] += (dt / 6.0) * (k1_cold[idx] + 2.0 * k2_cold[idx] + 2.0 * k3_cold[idx] + k4_cold[idx]);
        }
    }
}

double brayton_kernel(const KernelParams& params, double heater_outlet) {
    const double T1 = params.brayton_cooler_outlet_temp;
    const double T3 = max2(heater_outlet, T1 + 5.0);
    const double T2s = T1 * pow(params.brayton_pi_c, (params.brayton_gamma - 1.0) / params.brayton_gamma);
    const double T2 = T1 + (T2s - T1) / params.brayton_eta_c;
    const double T4s = T3 * pow(params.brayton_pi_t, -(params.brayton_gamma - 1.0) / params.brayton_gamma);
    const double T4 = T3 - params.brayton_eta_t * (T3 - T4s);
    const double requested_recuperation = params.brayton_recuperator_efficiency * max2(T4 - T2, 0.0);
    const double approach_limit = max2(T3 - params.brayton_min_heater_approach - T2, 0.0);
    const double delta_recuperation = requested_recuperation < approach_limit ? requested_recuperation : approach_limit;
    return T2 + delta_recuperation;
}

extern "C" void msr_step_kernel(
    StepState* state,
    DelayBundle* delays,
    const KernelParams* params,
    StepDiagnostics* diagnostics,
    int step
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=delays offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=diagnostics offset=slave bundle=gmem3
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=delays bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=diagnostics bundle=control
#pragma HLS INTERFACE s_axilite port=step bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    // Keep the AXI-backed structs aggregated at the interface boundary.
    // Internal kernels can then partition local state without forcing
    // unsupported disaggregation on the top-level m_axi ports.
    StepState local_state = *state;
    DelayBundle local_delays = *delays;
    const KernelParams local_params = *params;
    StepDiagnostics local_diagnostics{};
    CrossSections xs;
    double q_prime[kMaxN];

#pragma HLS ARRAY_PARTITION variable=local_state.C complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_state.phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx1_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx1_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx2_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx2_cold cyclic factor=kHeatExchangerLaneFactor dim=1

#pragma HLS ARRAY_PARTITION variable=local_params.beta complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.lambda_i complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.neutron_velocity complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.nu complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.chi_p complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.chi_d complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.d_e complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.rod_sigma_a_amplitude complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.external_reactivity_to_absorption complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.D_ref complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.D_ref cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.sigma_a_ref complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.sigma_a_ref cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.nu_sigma_f_ref complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.nu_sigma_f_ref cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.transverse_buckling_sq complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.transverse_buckling_sq cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_a_s complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_a_s cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_a_gr complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_a_gr cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_nu_sigma_f_s complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_nu_sigma_f_s cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_nu_sigma_f_gr complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_nu_sigma_f_gr cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_D_s complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_D_s cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.a_D_gr complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_D_gr cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.rod_shape complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.rod_shape cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_params.sigma_s12_ref cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_s12_s cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.a_sigma_s12_gr cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.T_s_ref cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.T_gr_ref cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.phi1_ref cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.phi2_ref cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.A_f cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.z cyclic factor=kCrossSectionLaneFactor dim=1

#pragma HLS ARRAY_PARTITION variable=xs.D complete dim=1
#pragma HLS ARRAY_PARTITION variable=xs.D cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=xs.sigma_a complete dim=1
#pragma HLS ARRAY_PARTITION variable=xs.sigma_a cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=xs.nu_sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=xs.nu_sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=xs.sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=xs.sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=xs.sigma_r complete dim=1
#pragma HLS ARRAY_PARTITION variable=xs.sigma_r cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=xs.sigma_s12 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=q_prime cyclic factor=kThermalLaneFactor dim=1

    cross_sections_kernel(local_params, local_state, 0.0, 0.0, xs);
    const double rho = estimate_global_rho(local_params, xs);
    neutronics_kernel(local_params, xs, local_state, q_prime);

    const double Ts_core_inlet = (local_params.core_inlet_mode == kCoreInletHxCoupled)
        ? delay_line_update(local_delays.hx_c, local_state.Ts_HX1_0, local_params.Ts_in, step)
        : local_params.Ts_in;
    thermal_kernel(local_params, q_prime, Ts_core_inlet, local_state);
    const double Ts_core_outlet = local_state.fuel[local_params.N - 1];

    const double Ts_HX1_L = delay_line_update(local_delays.c_hx, Ts_core_outlet, local_params.Ts_out, step);
    const double Tss_HX1_0 = delay_line_update(local_delays.r_hx, local_state.Tss_HX2_0, local_params.Tss_in, step);
    hx_kernel(
        local_params.Nx,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.hx1_dx,
        local_params.hx1_hot_velocity,
        local_params.hx1_cold_velocity,
        local_params.hx1_hot_exchange_coeff,
        local_params.hx1_cold_exchange_coeff,
        local_params.err,
        Ts_HX1_L,
        Tss_HX1_0,
        local_state.hx1_hot,
        local_state.hx1_cold
    );
    local_state.Ts_HX1_0 = local_state.hx1_hot[0];
    const double Tss_HX1_L = local_state.hx1_cold[local_params.Nx - 1];

    const double Tss_HX2_L = delay_line_update(local_delays.hx_r, Tss_HX1_L, local_params.Tss_out, step);
    const double Tsss_HX2_0 = delay_line_update(local_delays.pp_r, local_state.Tsss_pp_0, local_params.Tsss_in, step);
    hx_kernel(
        local_params.Nx,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.hx2_dx,
        local_params.hx2_hot_velocity,
        local_params.hx2_cold_velocity,
        local_params.hx2_hot_exchange_coeff,
        local_params.hx2_cold_exchange_coeff,
        local_params.err,
        Tss_HX2_L,
        Tsss_HX2_0,
        local_state.hx2_hot,
        local_state.hx2_cold
    );
    local_state.Tss_HX2_0 = local_state.hx2_hot[0];
    const double Tsss_HX2_L = local_state.hx2_cold[local_params.Nx - 1];

    const double Tsss_pp_L = delay_line_update(local_delays.r_pp, Tsss_HX2_L, local_params.Tsss_out, step);
    local_state.Tsss_pp_0 = brayton_kernel(local_params, Tsss_pp_L);

    const double phi_mid = local_state.phi1[local_params.N / 2] + local_state.phi2[local_params.N / 2];
    const double power = trapz_uniform(q_prime, local_params.z, local_params.N);

    local_diagnostics.phi_mid = phi_mid;
    local_diagnostics.rho = rho;
    local_diagnostics.power = power;
    local_diagnostics.fuel_mid = local_state.fuel[local_params.N / 2];
    local_diagnostics.graphite_mid = local_state.graphite[local_params.N / 2];
    local_diagnostics.core_inlet = Ts_core_inlet;
    local_diagnostics.core_outlet = Ts_core_outlet;
    local_diagnostics.hx1_hot_outlet = local_state.Ts_HX1_0;
    local_diagnostics.hx1_cold_outlet = Tss_HX1_L;
    local_diagnostics.hx2_hot_outlet = local_state.Tss_HX2_0;
    local_diagnostics.hx2_cold_outlet = Tsss_HX2_L;
    local_diagnostics.brayton_return = local_state.Tsss_pp_0;

    *state = local_state;
    *delays = local_delays;
    *diagnostics = local_diagnostics;
}

}  // namespace msr_vitis
