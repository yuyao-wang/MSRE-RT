#include "msr_vitis_kernel.cpp"

struct CoreStepState {
    double phi1[msr_vitis::kMaxN];
    double phi2[msr_vitis::kMaxN];
    double C[msr_vitis::kPrecursorGroups][msr_vitis::kMaxN];
    double fuel[msr_vitis::kMaxN];
    double graphite[msr_vitis::kMaxN];
    msr_vitis::PrecursorHistory precursor_history;
};

struct BopStepState {
    double hx1_hot[msr_vitis::kMaxN];
    double hx1_cold[msr_vitis::kMaxN];
    double hx2_hot[msr_vitis::kMaxN];
    double hx2_cold[msr_vitis::kMaxN];
};

struct CoreStepBoundary {
    double rho;
    double power;
    double phi_mid;
    double fuel_mid;
    double graphite_mid;
    double Ts_core_inlet;
    double Ts_core_outlet;
};

struct BopStepBoundary {
    double Ts_HX1_0;
    double Tss_HX1_L;
    double Tss_HX2_0;
    double Tsss_HX2_L;
    double Tsss_pp_0;
};

namespace {

using msr_vitis::CrossSections;
using msr_vitis::KernelParams;
using msr_vitis::PrecursorHistory;
using msr_vitis::StepState;

constexpr int kEnergyGroups = msr_vitis::kEnergyGroups;
constexpr int kPrecursorGroups = msr_vitis::kPrecursorGroups;
constexpr int kMaxLoopHistory = msr_vitis::kMaxLoopHistory;
constexpr int kMaxN = msr_vitis::kMaxN;
constexpr int kCrossSectionLaneFactor = msr_vitis::kCrossSectionLaneFactor;
constexpr int kNeutronicsLaneFactor = msr_vitis::kNeutronicsLaneFactor;
constexpr int kThermalLaneFactor = msr_vitis::kThermalLaneFactor;
constexpr int kHeatExchangerLaneFactor = msr_vitis::kHeatExchangerLaneFactor;

struct ThermalModuleState {
    double fuel[kMaxN];
    double graphite[kMaxN];
};

struct ThermalModuleParams {
    int N;
    int hardware_substeps;
    int use_graphite_axial_conduction;
    double dz;
    double outer_dt;
    double u_core;
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
};

struct HeatExchangerModuleState {
    double hot[kMaxN];
    double cold[kMaxN];
};

struct HeatExchangerModuleParams {
    int n;
    int hardware_substeps;
    double outer_dt;
    double dx;
    double hot_velocity;
    double cold_velocity;
    double hot_exchange_coeff;
    double cold_exchange_coeff;
    double err;
};

template <int FixedValue>
int resolve_fixed_value(int runtime_value) {
#pragma HLS INLINE
    return FixedValue > 0 ? FixedValue : runtime_value;
}

void copy_vector_in(int n, const double* src, double dst[kMaxN]) {
#pragma HLS INLINE
    for (int idx = 0; idx < n; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_GENERIC_SPATIAL_LOOP_MIN, MSR_GENERIC_SPATIAL_LOOP_MAX)
#pragma HLS PIPELINE II=1
        dst[idx] = src[idx];
    }
}

void copy_vector_out(int n, const double src[kMaxN], double* dst) {
#pragma HLS INLINE
    for (int idx = 0; idx < n; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_GENERIC_SPATIAL_LOOP_MIN, MSR_GENERIC_SPATIAL_LOOP_MAX)
#pragma HLS PIPELINE II=1
        dst[idx] = src[idx];
    }
}

void copy_precursor_vector_in(
    int n,
    const double src[kPrecursorGroups][kMaxN],
    double dst[kPrecursorGroups][kMaxN]
) {
#pragma HLS INLINE
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        copy_vector_in(n, src[group], dst[group]);
    }
}

void copy_energy_vector_in(
    int n,
    const double src[kEnergyGroups][kMaxN],
    double dst[kEnergyGroups][kMaxN]
) {
#pragma HLS INLINE
    for (int group = 0; group < kEnergyGroups; ++group) {
#pragma HLS UNROLL
        copy_vector_in(n, src[group], dst[group]);
    }
}

void copy_precursor_scalars(
    const double src[kPrecursorGroups],
    double dst[kPrecursorGroups]
) {
#pragma HLS INLINE
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        dst[group] = src[group];
    }
}

void copy_energy_scalars(
    const double src[kEnergyGroups],
    double dst[kEnergyGroups]
) {
#pragma HLS INLINE
    for (int group = 0; group < kEnergyGroups; ++group) {
#pragma HLS UNROLL
        dst[group] = src[group];
    }
}

void copy_precursor_history(
    const PrecursorHistory& src,
    PrecursorHistory& dst
) {
#pragma HLS INLINE
    for (int group = 0; group < kPrecursorGroups; ++group) {
        for (int idx = 0; idx < kMaxLoopHistory; ++idx) {
#pragma HLS PIPELINE II=1
            dst.outlet_history[group][idx] = src.outlet_history[group][idx];
        }
        dst.last_outlet[group] = src.last_outlet[group];
    }
    dst.write_index = src.write_index;
    dst.valid_count = src.valid_count;
}

void load_neutronics_module_state(int n, const StepState* src, StepState& dst) {
#pragma HLS INLINE
    copy_vector_in(n, src->phi1, dst.phi1);
    copy_vector_in(n, src->phi2, dst.phi2);
    copy_precursor_vector_in(n, src->C, dst.C);
    copy_precursor_history(src->precursor_history, dst.precursor_history);
}

void store_neutronics_module_state(int n, const StepState& src, StepState* dst) {
#pragma HLS INLINE
    copy_vector_out(n, src.phi1, dst->phi1);
    copy_vector_out(n, src.phi2, dst->phi2);
    copy_precursor_vector_in(n, src.C, dst->C);
    copy_precursor_history(src.precursor_history, dst->precursor_history);
}

void load_neutronics_module_params(const KernelParams* src, KernelParams& dst) {
#pragma HLS INLINE
    dst.N = src->N;
    dst.hardware_substeps = src->hardware_substeps;
    dst.inlet_mode = src->inlet_mode;
    dst.precursor_delay_older = src->precursor_delay_older;
    dst.precursor_delay_newer = src->precursor_delay_newer;
    dst.precursor_interp_newer = src->precursor_interp_newer;
    dst.dz = src->dz;
    dst.outer_dt = src->outer_dt;
    dst.u_precursor = src->u_precursor;
    dst.power_scale = src->power_scale;
    dst.Beta = src->Beta;
    dst.precursor_loop_efficiency = src->precursor_loop_efficiency;
    dst.precursor_loop_tau = src->precursor_loop_tau;
    copy_precursor_scalars(src->beta, dst.beta);
    copy_precursor_scalars(src->lambda_i, dst.lambda_i);
    copy_energy_scalars(src->neutron_velocity, dst.neutron_velocity);
    copy_energy_scalars(src->chi_p, dst.chi_p);
    copy_energy_scalars(src->chi_d, dst.chi_d);
    copy_energy_scalars(src->d_e, dst.d_e);
    copy_vector_in(dst.N, src->A_f, dst.A_f);
}

void load_neutronics_cross_sections(int n, const CrossSections* src, CrossSections& dst) {
#pragma HLS INLINE
    copy_energy_vector_in(n, src->D, dst.D);
    copy_vector_in(n, src->sigma_s12, dst.sigma_s12);
    copy_energy_vector_in(n, src->nu_sigma_f, dst.nu_sigma_f);
    copy_energy_vector_in(n, src->sigma_f, dst.sigma_f);
    copy_energy_vector_in(n, src->sigma_r, dst.sigma_r);
}

void load_thermal_module_state(int n, const StepState* src, ThermalModuleState& dst) {
#pragma HLS INLINE
    copy_vector_in(n, src->fuel, dst.fuel);
    copy_vector_in(n, src->graphite, dst.graphite);
}

void store_thermal_module_state(int n, const ThermalModuleState& src, StepState* dst) {
#pragma HLS INLINE
    copy_vector_out(n, src.fuel, dst->fuel);
    copy_vector_out(n, src.graphite, dst->graphite);
}

ThermalModuleParams load_thermal_module_params(const KernelParams* src) {
#pragma HLS INLINE
    ThermalModuleParams dst{};
    dst.N = src->N;
    dst.hardware_substeps = src->hardware_substeps;
    dst.use_graphite_axial_conduction = src->use_graphite_axial_conduction;
    dst.dz = src->dz;
    dst.outer_dt = src->outer_dt;
    dst.u_core = src->u_core;
    dst.rho_s = src->rho_s;
    dst.c_p_s = src->c_p_s;
    dst.A_s = src->A_s;
    dst.rho_gr = src->rho_gr;
    dst.c_p_g = src->c_p_g;
    dst.A_gr = src->A_gr;
    dst.h_sgr = src->h_sgr;
    dst.P_sgr = src->P_sgr;
    dst.k_gr = src->k_gr;
    dst.eta_s = src->eta_s;
    dst.eta_gr = src->eta_gr;
    dst.err = src->err;
    return dst;
}

void load_heat_exchanger_module_state(
    int n,
    const double* hot_src,
    const double* cold_src,
    HeatExchangerModuleState& dst
) {
#pragma HLS INLINE
    copy_vector_in(n, hot_src, dst.hot);
    copy_vector_in(n, cold_src, dst.cold);
}

void store_heat_exchanger_module_state(
    int n,
    const HeatExchangerModuleState& src,
    double* hot_dst,
    double* cold_dst
) {
#pragma HLS INLINE
    copy_vector_out(n, src.hot, hot_dst);
    copy_vector_out(n, src.cold, cold_dst);
}

HeatExchangerModuleParams load_hx1_module_params(const KernelParams* src) {
#pragma HLS INLINE
    HeatExchangerModuleParams dst{};
    dst.n = src->Nx;
    dst.hardware_substeps = src->hardware_substeps;
    dst.outer_dt = src->outer_dt;
    dst.dx = src->hx1_dx;
    dst.hot_velocity = src->hx1_hot_velocity;
    dst.cold_velocity = src->hx1_cold_velocity;
    dst.hot_exchange_coeff = src->hx1_hot_exchange_coeff;
    dst.cold_exchange_coeff = src->hx1_cold_exchange_coeff;
    dst.err = src->err;
    return dst;
}

HeatExchangerModuleParams load_hx2_module_params(const KernelParams* src) {
#pragma HLS INLINE
    HeatExchangerModuleParams dst{};
    dst.n = src->Nx;
    dst.hardware_substeps = src->hardware_substeps;
    dst.outer_dt = src->outer_dt;
    dst.dx = src->hx2_dx;
    dst.hot_velocity = src->hx2_hot_velocity;
    dst.cold_velocity = src->hx2_cold_velocity;
    dst.hot_exchange_coeff = src->hx2_hot_exchange_coeff;
    dst.cold_exchange_coeff = src->hx2_cold_exchange_coeff;
    dst.err = src->err;
    return dst;
}

void load_core_step_state(int n, const CoreStepState* src, StepState& dst) {
#pragma HLS INLINE
    copy_vector_in(n, src->phi1, dst.phi1);
    copy_vector_in(n, src->phi2, dst.phi2);
    copy_precursor_vector_in(n, src->C, dst.C);
    copy_vector_in(n, src->fuel, dst.fuel);
    copy_vector_in(n, src->graphite, dst.graphite);
    copy_precursor_history(src->precursor_history, dst.precursor_history);
}

void store_core_step_state(int n, const StepState& src, CoreStepState* dst) {
#pragma HLS INLINE
    copy_vector_out(n, src.phi1, dst->phi1);
    copy_vector_out(n, src.phi2, dst->phi2);
    copy_precursor_vector_in(n, src.C, dst->C);
    copy_vector_out(n, src.fuel, dst->fuel);
    copy_vector_out(n, src.graphite, dst->graphite);
    copy_precursor_history(src.precursor_history, dst->precursor_history);
}

void load_core_step_params(
    int n,
    int hardware_substeps,
    const KernelParams* src,
    KernelParams& dst
) {
#pragma HLS INLINE
    dst.N = n;
    dst.hardware_substeps = hardware_substeps;
    dst.inlet_mode = src->inlet_mode;
    dst.use_graphite_axial_conduction = src->use_graphite_axial_conduction;
    dst.precursor_delay_older = src->precursor_delay_older;
    dst.precursor_delay_newer = src->precursor_delay_newer;
    dst.precursor_interp_newer = src->precursor_interp_newer;
    dst.dz = src->dz;
    dst.outer_dt = src->outer_dt;
    dst.u_core = src->u_core;
    dst.u_precursor = src->u_precursor;
    dst.power_scale = src->power_scale;
    dst.Beta = src->Beta;
    dst.min_diffusion = src->min_diffusion;
    dst.min_cross_section = src->min_cross_section;
    dst.reference_multiplication_ratio = src->reference_multiplication_ratio;
    dst.precursor_loop_efficiency = src->precursor_loop_efficiency;
    dst.precursor_loop_tau = src->precursor_loop_tau;
    dst.rho_s = src->rho_s;
    dst.c_p_s = src->c_p_s;
    dst.A_s = src->A_s;
    dst.rho_gr = src->rho_gr;
    dst.c_p_g = src->c_p_g;
    dst.A_gr = src->A_gr;
    dst.h_sgr = src->h_sgr;
    dst.P_sgr = src->P_sgr;
    dst.k_gr = src->k_gr;
    dst.eta_s = src->eta_s;
    dst.eta_gr = src->eta_gr;
    dst.err = src->err;

    copy_precursor_scalars(src->beta, dst.beta);
    copy_precursor_scalars(src->lambda_i, dst.lambda_i);
    copy_energy_scalars(src->neutron_velocity, dst.neutron_velocity);
    copy_energy_scalars(src->nu, dst.nu);
    copy_energy_scalars(src->chi_p, dst.chi_p);
    copy_energy_scalars(src->chi_d, dst.chi_d);
    copy_energy_scalars(src->d_e, dst.d_e);
    copy_energy_scalars(src->rod_sigma_a_amplitude, dst.rod_sigma_a_amplitude);
    copy_energy_scalars(src->external_reactivity_to_absorption, dst.external_reactivity_to_absorption);

    copy_energy_vector_in(dst.N, src->D_ref, dst.D_ref);
    copy_energy_vector_in(dst.N, src->sigma_a_ref, dst.sigma_a_ref);
    copy_vector_in(dst.N, src->sigma_s12_ref, dst.sigma_s12_ref);
    copy_energy_vector_in(dst.N, src->nu_sigma_f_ref, dst.nu_sigma_f_ref);
    copy_energy_vector_in(dst.N, src->transverse_buckling_sq, dst.transverse_buckling_sq);
    copy_energy_vector_in(dst.N, src->a_sigma_a_s, dst.a_sigma_a_s);
    copy_energy_vector_in(dst.N, src->a_sigma_a_gr, dst.a_sigma_a_gr);
    copy_vector_in(dst.N, src->a_sigma_s12_s, dst.a_sigma_s12_s);
    copy_vector_in(dst.N, src->a_sigma_s12_gr, dst.a_sigma_s12_gr);
    copy_energy_vector_in(dst.N, src->a_nu_sigma_f_s, dst.a_nu_sigma_f_s);
    copy_energy_vector_in(dst.N, src->a_nu_sigma_f_gr, dst.a_nu_sigma_f_gr);
    copy_energy_vector_in(dst.N, src->a_D_s, dst.a_D_s);
    copy_energy_vector_in(dst.N, src->a_D_gr, dst.a_D_gr);
    copy_energy_vector_in(dst.N, src->rod_shape, dst.rod_shape);
    copy_vector_in(dst.N, src->T_s_ref, dst.T_s_ref);
    copy_vector_in(dst.N, src->T_gr_ref, dst.T_gr_ref);
    copy_vector_in(dst.N, src->phi1_ref, dst.phi1_ref);
    copy_vector_in(dst.N, src->phi2_ref, dst.phi2_ref);
    copy_vector_in(dst.N, src->A_f, dst.A_f);
    copy_vector_in(dst.N, src->z, dst.z);
}

void load_core_step_params(const KernelParams* src, KernelParams& dst) {
#pragma HLS INLINE
    load_core_step_params(src->N, src->hardware_substeps, src, dst);
}

void load_bop_step_state(int n, const BopStepState* src, BopStepState& dst) {
#pragma HLS INLINE
    copy_vector_in(n, src->hx1_hot, dst.hx1_hot);
    copy_vector_in(n, src->hx1_cold, dst.hx1_cold);
    copy_vector_in(n, src->hx2_hot, dst.hx2_hot);
    copy_vector_in(n, src->hx2_cold, dst.hx2_cold);
}

void store_bop_step_state(int n, const BopStepState& src, BopStepState* dst) {
#pragma HLS INLINE
    copy_vector_out(n, src.hx1_hot, dst->hx1_hot);
    copy_vector_out(n, src.hx1_cold, dst->hx1_cold);
    copy_vector_out(n, src.hx2_hot, dst->hx2_hot);
    copy_vector_out(n, src.hx2_cold, dst->hx2_cold);
}

void load_bop_step_params(
    int n,
    int hardware_substeps,
    const KernelParams* src,
    KernelParams& dst
) {
#pragma HLS INLINE
    dst.Nx = n;
    dst.hardware_substeps = hardware_substeps;
    dst.outer_dt = src->outer_dt;
    dst.err = src->err;

    dst.hx1_dx = src->hx1_dx;
    dst.hx1_hot_velocity = src->hx1_hot_velocity;
    dst.hx1_cold_velocity = src->hx1_cold_velocity;
    dst.hx1_hot_exchange_coeff = src->hx1_hot_exchange_coeff;
    dst.hx1_cold_exchange_coeff = src->hx1_cold_exchange_coeff;

    dst.hx2_dx = src->hx2_dx;
    dst.hx2_hot_velocity = src->hx2_hot_velocity;
    dst.hx2_cold_velocity = src->hx2_cold_velocity;
    dst.hx2_hot_exchange_coeff = src->hx2_hot_exchange_coeff;
    dst.hx2_cold_exchange_coeff = src->hx2_cold_exchange_coeff;

    dst.brayton_gamma = src->brayton_gamma;
    dst.brayton_eta_c = src->brayton_eta_c;
    dst.brayton_eta_t = src->brayton_eta_t;
    dst.brayton_pi_c = src->brayton_pi_c;
    dst.brayton_pi_t = src->brayton_pi_t;
    dst.brayton_recuperator_efficiency = src->brayton_recuperator_efficiency;
    dst.brayton_cooler_outlet_temp = src->brayton_cooler_outlet_temp;
    dst.brayton_min_heater_approach = src->brayton_min_heater_approach;
    dst.brayton_mdot = src->brayton_mdot;
    dst.c_p_sss = src->c_p_sss;
}

void load_bop_step_params(const KernelParams* src, KernelParams& dst) {
#pragma HLS INLINE
    load_bop_step_params(src->Nx, src->hardware_substeps, src, dst);
}

void thermal_rhs_module(
    const ThermalModuleParams& params,
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
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
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

void load_thermal_stage_module(
    int n,
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
    for (int idx = 0; idx < n; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
        fuel_stage[idx] = fuel[idx] + scale * dfuel[idx];
        graphite_stage[idx] = graphite[idx] + scale * dgraphite[idx];
    }
}

void thermal_kernel_module(
    const ThermalModuleParams& params,
    const double q_prime[kMaxN],
    double Ts_core_inlet,
    ThermalModuleState& state
) {
    const double dt = params.outer_dt / static_cast<double>(params.hardware_substeps);
    for (int substep = 0; substep < params.hardware_substeps; ++substep) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_SUBSTEP_LOOP_MIN, MSR_SUBSTEP_LOOP_MAX)
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
        thermal_rhs_module(params, q_prime, Ts_core_inlet, state.fuel, state.graphite, k1_fuel, k1_graphite);
        load_thermal_stage_module(params.N, 0.5 * dt, state.fuel, state.graphite, k1_fuel, k1_graphite, fuel_stage, graphite_stage);
        thermal_rhs_module(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k2_fuel, k2_graphite);
        load_thermal_stage_module(params.N, 0.5 * dt, state.fuel, state.graphite, k2_fuel, k2_graphite, fuel_stage, graphite_stage);
        thermal_rhs_module(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k3_fuel, k3_graphite);
        load_thermal_stage_module(params.N, dt, state.fuel, state.graphite, k3_fuel, k3_graphite, fuel_stage, graphite_stage);
        thermal_rhs_module(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k4_fuel, k4_graphite);

        for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
            state.fuel[idx] += (dt / 6.0) * (k1_fuel[idx] + 2.0 * k2_fuel[idx] + 2.0 * k3_fuel[idx] + k4_fuel[idx]);
            state.graphite[idx] += (dt / 6.0) * (k1_graphite[idx] + 2.0 * k2_graphite[idx] + 2.0 * k3_graphite[idx] + k4_graphite[idx]);
        }
        state.fuel[0] = Ts_core_inlet;
    }
}

}  // namespace

extern "C" void msr_cross_sections_bench(
    const StepState* state,
    const KernelParams* params,
    double rod_position,
    double external_reactivity,
    CrossSections* xs_out,
    double* rho_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=xs_out offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=rho_out offset=slave bundle=gmem3
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=rod_position bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivity bundle=control
#pragma HLS INTERFACE s_axilite port=xs_out bundle=control
#pragma HLS INTERFACE s_axilite port=rho_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    StepState local_state = *state;
    const KernelParams local_params = *params;
    CrossSections local_xs;

#pragma HLS ARRAY_PARTITION variable=local_state.fuel cyclic factor=kCrossSectionLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.graphite cyclic factor=kCrossSectionLaneFactor dim=1

#pragma HLS ARRAY_PARTITION variable=local_params.nu complete dim=1
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
#pragma HLS ARRAY_PARTITION variable=local_params.z cyclic factor=kCrossSectionLaneFactor dim=1

#pragma HLS ARRAY_PARTITION variable=local_xs.D complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.D cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r cyclic factor=kCrossSectionLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_s12 cyclic factor=kCrossSectionLaneFactor dim=1

    msr_vitis::cross_sections_kernel(local_params, local_state, rod_position, external_reactivity, local_xs);
    rho_out[0] = msr_vitis::estimate_global_rho(local_params, local_xs);
    *xs_out = local_xs;
}

extern "C" void msr_neutronics_bench(
    StepState* state,
    const KernelParams* params,
    const CrossSections* xs_in,
    double* q_prime_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=xs_in offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=q_prime_out offset=slave bundle=gmem3
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=xs_in bundle=control
#pragma HLS INTERFACE s_axilite port=q_prime_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    StepState local_state{};
    KernelParams local_params{};
    CrossSections local_xs{};
    double local_q_prime[kMaxN];

    load_neutronics_module_params(params, local_params);
    load_neutronics_module_state(local_params.N, state, local_state);
    load_neutronics_cross_sections(local_params.N, xs_in, local_xs);

#pragma HLS ARRAY_PARTITION variable=local_state.C complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_state.phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.phi2 cyclic factor=kNeutronicsLaneFactor dim=1

#pragma HLS ARRAY_PARTITION variable=local_params.beta complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.lambda_i complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.neutron_velocity complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.chi_p complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.chi_d complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_params.d_e complete dim=1

#pragma HLS ARRAY_PARTITION variable=local_xs.D complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.D cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_s12 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_q_prime cyclic factor=kNeutronicsLaneFactor dim=1

    msr_vitis::neutronics_kernel(local_params, local_xs, local_state, local_q_prime);

    store_neutronics_module_state(local_params.N, local_state, state);
    copy_vector_out(local_params.N, local_q_prime, q_prime_out);
}

extern "C" void msr_thermal_bench(
    StepState* state,
    const KernelParams* params,
    const double* q_prime_in,
    double Ts_core_inlet
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=q_prime_in offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=q_prime_in bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_core_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const ThermalModuleParams local_params = load_thermal_module_params(params);
    ThermalModuleState local_state{};
    double local_q_prime[kMaxN];

#pragma HLS ARRAY_PARTITION variable=local_state.fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_q_prime cyclic factor=kThermalLaneFactor dim=1

    load_thermal_module_state(local_params.N, state, local_state);
    copy_vector_in(local_params.N, q_prime_in, local_q_prime);
    thermal_kernel_module(local_params, local_q_prime, Ts_core_inlet, local_state);
    store_thermal_module_state(local_params.N, local_state, state);
}

extern "C" void msr_hx1_bench(
    StepState* state,
    const KernelParams* params,
    double hot_inlet,
    double cold_inlet
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=hot_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=cold_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const HeatExchangerModuleParams local_params = load_hx1_module_params(params);
    HeatExchangerModuleState local_state{};

    load_heat_exchanger_module_state(local_params.n, state->hx1_hot, state->hx1_cold, local_state);

#pragma HLS ARRAY_PARTITION variable=local_state.hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.cold cyclic factor=kHeatExchangerLaneFactor dim=1

    msr_vitis::hx_kernel(
        local_params.n,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.dx,
        local_params.hot_velocity,
        local_params.cold_velocity,
        local_params.hot_exchange_coeff,
        local_params.cold_exchange_coeff,
        local_params.err,
        hot_inlet,
        cold_inlet,
        local_state.hot,
        local_state.cold
    );

    store_heat_exchanger_module_state(local_params.n, local_state, state->hx1_hot, state->hx1_cold);
}

extern "C" void msr_hx2_bench(
    StepState* state,
    const KernelParams* params,
    double hot_inlet,
    double cold_inlet
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=hot_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=cold_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const HeatExchangerModuleParams local_params = load_hx2_module_params(params);
    HeatExchangerModuleState local_state{};

    load_heat_exchanger_module_state(local_params.n, state->hx2_hot, state->hx2_cold, local_state);

#pragma HLS ARRAY_PARTITION variable=local_state.hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.cold cyclic factor=kHeatExchangerLaneFactor dim=1

    msr_vitis::hx_kernel(
        local_params.n,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.dx,
        local_params.hot_velocity,
        local_params.cold_velocity,
        local_params.hot_exchange_coeff,
        local_params.cold_exchange_coeff,
        local_params.err,
        hot_inlet,
        cold_inlet,
        local_state.hot,
        local_state.cold
    );

    store_heat_exchanger_module_state(local_params.n, local_state, state->hx2_hot, state->hx2_cold);
}

template <int FixedN, int FixedSubsteps>
void core_step_kernel_impl(
    CoreStepState* state,
    const KernelParams* params,
    double Ts_core_inlet,
    double rod_position,
    double external_reactivity,
    CoreStepBoundary* boundary_out
) {
    StepState local_state;
    KernelParams local_params;
    CrossSections local_xs;
    double local_q_prime[kMaxN];
    const int core_n = resolve_fixed_value<FixedN>(params->N);
    const int hardware_substeps = resolve_fixed_value<FixedSubsteps>(params->hardware_substeps);
    const int core_mid = core_n / 2;
    const int core_last = core_n - 1;

    load_core_step_params(core_n, hardware_substeps, params, local_params);
    load_core_step_state(core_n, state, local_state);

#pragma HLS ARRAY_PARTITION variable=local_state.C complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_state.phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.graphite cyclic factor=kThermalLaneFactor dim=1

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

#pragma HLS ARRAY_PARTITION variable=local_xs.D complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.D cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_s12 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_q_prime cyclic factor=kThermalLaneFactor dim=1

    msr_vitis::cross_sections_kernel(local_params, local_state, rod_position, external_reactivity, local_xs);
    const double rho = msr_vitis::estimate_global_rho(local_params, local_xs);
    msr_vitis::neutronics_kernel(local_params, local_xs, local_state, local_q_prime);
    msr_vitis::thermal_kernel(local_params, local_q_prime, Ts_core_inlet, local_state);

    const double Ts_core_outlet = local_state.fuel[core_last];
    const double phi_mid = local_state.phi1[core_mid] + local_state.phi2[core_mid];
    const double power = msr_vitis::trapz_uniform(local_q_prime, local_params.z, core_n);

    store_core_step_state(core_n, local_state, state);

    boundary_out->rho = rho;
    boundary_out->power = power;
    boundary_out->phi_mid = phi_mid;
    boundary_out->fuel_mid = local_state.fuel[core_mid];
    boundary_out->graphite_mid = local_state.graphite[core_mid];
    boundary_out->Ts_core_inlet = Ts_core_inlet;
    boundary_out->Ts_core_outlet = Ts_core_outlet;
}

extern "C" void core_step_kernel(
    CoreStepState* state,
    const KernelParams* params,
    double Ts_core_inlet,
    double rod_position,
    double external_reactivity,
    CoreStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_core_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=rod_position bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivity bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    core_step_kernel_impl<0, 0>(state, params, Ts_core_inlet, rod_position, external_reactivity, boundary_out);
}

extern "C" void core_step_kernel_n80_s1(
    CoreStepState* state,
    const KernelParams* params,
    double Ts_core_inlet,
    double rod_position,
    double external_reactivity,
    CoreStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_core_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=rod_position bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivity bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    core_step_kernel_impl<80, 1>(state, params, Ts_core_inlet, rod_position, external_reactivity, boundary_out);
}

extern "C" void core_step_kernel_n200_s1(
    CoreStepState* state,
    const KernelParams* params,
    double Ts_core_inlet,
    double rod_position,
    double external_reactivity,
    CoreStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_core_inlet bundle=control
#pragma HLS INTERFACE s_axilite port=rod_position bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivity bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    core_step_kernel_impl<200, 1>(state, params, Ts_core_inlet, rod_position, external_reactivity, boundary_out);
}

template <int FixedNx, int FixedSubsteps>
void bop_step_kernel_impl(
    BopStepState* state,
    const KernelParams* params,
    double Ts_HX1_L,
    double Tss_HX1_0,
    double Tss_HX2_L,
    double Tsss_HX2_0,
    BopStepBoundary* boundary_out
) {
    BopStepState local_state;
    KernelParams local_params;
    const int bop_n = resolve_fixed_value<FixedNx>(params->Nx);
    const int hardware_substeps = resolve_fixed_value<FixedSubsteps>(params->hardware_substeps);
    const int bop_last = bop_n - 1;

    load_bop_step_params(bop_n, hardware_substeps, params, local_params);
    load_bop_step_state(bop_n, state, local_state);

#pragma HLS ARRAY_PARTITION variable=local_state.hx1_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx1_cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx2_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx2_cold cyclic factor=kHeatExchangerLaneFactor dim=1

    msr_vitis::hx_kernel(
        bop_n,
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
    const double Ts_HX1_0 = local_state.hx1_hot[0];
    const double Tss_HX1_L = local_state.hx1_cold[bop_last];

    msr_vitis::hx_kernel(
        bop_n,
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
    const double Tss_HX2_0 = local_state.hx2_hot[0];
    const double Tsss_HX2_L = local_state.hx2_cold[bop_last];
    const double Tsss_pp_0 = msr_vitis::brayton_kernel(local_params, Tsss_HX2_L);

    store_bop_step_state(bop_n, local_state, state);

    boundary_out->Ts_HX1_0 = Ts_HX1_0;
    boundary_out->Tss_HX1_L = Tss_HX1_L;
    boundary_out->Tss_HX2_0 = Tss_HX2_0;
    boundary_out->Tsss_HX2_L = Tsss_HX2_L;
    boundary_out->Tsss_pp_0 = Tsss_pp_0;
}

extern "C" void bop_step_kernel(
    BopStepState* state,
    const KernelParams* params,
    double Ts_HX1_L,
    double Tss_HX1_0,
    double Tss_HX2_L,
    double Tsss_HX2_0,
    BopStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_HX1_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX1_0 bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX2_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tsss_HX2_0 bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    bop_step_kernel_impl<0, 0>(state, params, Ts_HX1_L, Tss_HX1_0, Tss_HX2_L, Tsss_HX2_0, boundary_out);
}

extern "C" void bop_step_kernel_n80_s1(
    BopStepState* state,
    const KernelParams* params,
    double Ts_HX1_L,
    double Tss_HX1_0,
    double Tss_HX2_L,
    double Tsss_HX2_0,
    BopStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_HX1_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX1_0 bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX2_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tsss_HX2_0 bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    bop_step_kernel_impl<80, 1>(state, params, Ts_HX1_L, Tss_HX1_0, Tss_HX2_L, Tsss_HX2_0, boundary_out);
}

extern "C" void bop_step_kernel_n200_s1(
    BopStepState* state,
    const KernelParams* params,
    double Ts_HX1_L,
    double Tss_HX1_0,
    double Tss_HX2_L,
    double Tsss_HX2_0,
    BopStepBoundary* boundary_out
) {
#pragma HLS INTERFACE m_axi port=state offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=boundary_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=state bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=Ts_HX1_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX1_0 bundle=control
#pragma HLS INTERFACE s_axilite port=Tss_HX2_L bundle=control
#pragma HLS INTERFACE s_axilite port=Tsss_HX2_0 bundle=control
#pragma HLS INTERFACE s_axilite port=boundary_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    bop_step_kernel_impl<200, 1>(state, params, Ts_HX1_L, Tss_HX1_0, Tss_HX2_L, Tsss_HX2_0, boundary_out);
}

extern "C" void msr_power_reduction_bench(
    const KernelParams* params,
    const double* q_prime_in,
    double* power_out
) {
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=q_prime_in offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=power_out offset=slave bundle=gmem2
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=q_prime_in bundle=control
#pragma HLS INTERFACE s_axilite port=power_out bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    const KernelParams local_params = *params;
    double local_q_prime[kMaxN];

#pragma HLS ARRAY_PARTITION variable=local_params.z cyclic factor=kCrossSectionLaneFactor dim=1

    copy_vector_in(local_params.N, q_prime_in, local_q_prime);
    power_out[0] = msr_vitis::trapz_uniform(local_q_prime, local_params.z, local_params.N);
}
