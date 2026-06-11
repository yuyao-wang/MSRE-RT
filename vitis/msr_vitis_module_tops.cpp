#include "msr_vitis_kernel.cpp"

namespace {

using msr_vitis::CrossSections;
using msr_vitis::KernelParams;
using msr_vitis::StepState;

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

void copy_vector_in(int n, const double* src, double dst[kMaxN]) {
#pragma HLS INLINE
    for (int idx = 0; idx < n; ++idx) {
#pragma HLS PIPELINE II=1
        dst[idx] = src[idx];
    }
}

void copy_vector_out(int n, const double src[kMaxN], double* dst) {
#pragma HLS INLINE
    for (int idx = 0; idx < n; ++idx) {
#pragma HLS PIPELINE II=1
        dst[idx] = src[idx];
    }
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

    StepState local_state = *state;
    const KernelParams local_params = *params;
    CrossSections local_xs = *xs_in;
    double local_q_prime[kMaxN];

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
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_a cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.nu_sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_f cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r complete dim=1
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_r cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=local_xs.sigma_s12 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_q_prime cyclic factor=kNeutronicsLaneFactor dim=1

    msr_vitis::neutronics_kernel(local_params, local_xs, local_state, local_q_prime);

    *state = local_state;
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

    StepState local_state = *state;
    const KernelParams local_params = *params;

#pragma HLS ARRAY_PARTITION variable=local_state.hx1_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx1_cold cyclic factor=kHeatExchangerLaneFactor dim=1

    msr_vitis::hx_kernel(
        local_params.Nx,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.hx1_dx,
        local_params.hx1_hot_velocity,
        local_params.hx1_cold_velocity,
        local_params.hx1_hot_exchange_coeff,
        local_params.hx1_cold_exchange_coeff,
        local_params.err,
        hot_inlet,
        cold_inlet,
        local_state.hx1_hot,
        local_state.hx1_cold
    );

    *state = local_state;
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

    StepState local_state = *state;
    const KernelParams local_params = *params;

#pragma HLS ARRAY_PARTITION variable=local_state.hx2_hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.hx2_cold cyclic factor=kHeatExchangerLaneFactor dim=1

    msr_vitis::hx_kernel(
        local_params.Nx,
        local_params.hardware_substeps,
        local_params.outer_dt,
        local_params.hx2_dx,
        local_params.hx2_hot_velocity,
        local_params.hx2_cold_velocity,
        local_params.hx2_hot_exchange_coeff,
        local_params.hx2_cold_exchange_coeff,
        local_params.err,
        hot_inlet,
        cold_inlet,
        local_state.hx2_hot,
        local_state.hx2_cold
    );

    *state = local_state;
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
