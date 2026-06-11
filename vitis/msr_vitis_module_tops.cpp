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

    StepState local_state = *state;
    const KernelParams local_params = *params;
    double local_q_prime[kMaxN];

#pragma HLS ARRAY_PARTITION variable=local_state.fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_state.graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=local_q_prime cyclic factor=kThermalLaneFactor dim=1

    copy_vector_in(local_params.N, q_prime_in, local_q_prime);
    msr_vitis::thermal_kernel(local_params, local_q_prime, Ts_core_inlet, local_state);
    *state = local_state;
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
