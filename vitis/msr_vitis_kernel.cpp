#include <math.h>

#include "../point_kinetics_shared.hpp"

namespace msr_vitis {

#ifndef MSR_CROSS_SECTION_LANE_FACTOR
#define MSR_CROSS_SECTION_LANE_FACTOR 4
#endif

#ifndef MSR_NEUTRONICS_LANE_FACTOR
#define MSR_NEUTRONICS_LANE_FACTOR 8
#endif

#ifndef MSR_THERMAL_LANE_FACTOR
#define MSR_THERMAL_LANE_FACTOR 8
#endif

#ifndef MSR_HEAT_EXCHANGER_LANE_FACTOR
#define MSR_HEAT_EXCHANGER_LANE_FACTOR 4
#endif

#ifndef MSR_FIXED_CORE_N
#define MSR_FIXED_CORE_N 0
#endif

#ifndef MSR_FIXED_BOP_NX
#define MSR_FIXED_BOP_NX 0
#endif

#ifndef MSR_FIXED_HARDWARE_SUBSTEPS
#define MSR_FIXED_HARDWARE_SUBSTEPS 0
#endif

#ifndef MSR_MAX_STATE_N
#define MSR_MAX_STATE_N 128
#endif

#ifndef MSR_MAX_HARDWARE_SUBSTEPS
#define MSR_MAX_HARDWARE_SUBSTEPS 32
#endif

#ifndef MSR_MAX_TRANSIENT_STEPS
#define MSR_MAX_TRANSIENT_STEPS 4096
#endif

#ifndef MSR_MAX_BATCH_SCENARIOS
#define MSR_MAX_BATCH_SCENARIOS 64
#endif

#ifndef MSR_RESIDENT_THERMAL_FLOAT
#define MSR_RESIDENT_THERMAL_FLOAT 1
#endif

#ifndef MSR_RESIDENT_HISTORY_FLOAT
#define MSR_RESIDENT_HISTORY_FLOAT 1
#endif

#ifndef MSR_BATCH_CONTROL_FLOAT
#define MSR_BATCH_CONTROL_FLOAT 1
#endif

#ifndef MSR_PRECURSOR_ANALYTIC_UPDATE
#define MSR_PRECURSOR_ANALYTIC_UPDATE 1
#endif

#ifndef MSR_SHARED_FPU_MODE
#define MSR_SHARED_FPU_MODE 0
#endif

#ifndef MSR_BATCH_BENCH_STEP_COUNT
#define MSR_BATCH_BENCH_STEP_COUNT 600
#endif

#ifndef MSR_BATCH_BENCH_SCENARIO_COUNT
#define MSR_BATCH_BENCH_SCENARIO_COUNT 1
#endif

#define MSR_HLS_STRINGIFY_IMPL(x) #x
#define MSR_HLS_STRINGIFY(x) MSR_HLS_STRINGIFY_IMPL(x)
#define MSR_HLS_LOOP_TRIPCOUNT(min_v, max_v) _Pragma(MSR_HLS_STRINGIFY(HLS LOOP_TRIPCOUNT min=min_v max=max_v))

#if MSR_FIXED_CORE_N > 0
#define MSR_CORE_SPATIAL_LOOP_MIN MSR_FIXED_CORE_N
#define MSR_CORE_SPATIAL_LOOP_MAX MSR_FIXED_CORE_N
#define MSR_CORE_SPATIAL_MINUS_ONE_LOOP_MIN (MSR_FIXED_CORE_N - 1)
#define MSR_CORE_SPATIAL_MINUS_ONE_LOOP_MAX (MSR_FIXED_CORE_N - 1)
#else
#define MSR_CORE_SPATIAL_LOOP_MIN 1
#define MSR_CORE_SPATIAL_LOOP_MAX MSR_MAX_STATE_N
#define MSR_CORE_SPATIAL_MINUS_ONE_LOOP_MIN 0
#define MSR_CORE_SPATIAL_MINUS_ONE_LOOP_MAX (MSR_MAX_STATE_N - 1)
#endif

#if MSR_FIXED_BOP_NX > 0
#define MSR_BOP_SPATIAL_LOOP_MIN MSR_FIXED_BOP_NX
#define MSR_BOP_SPATIAL_LOOP_MAX MSR_FIXED_BOP_NX
#else
#define MSR_BOP_SPATIAL_LOOP_MIN 1
#define MSR_BOP_SPATIAL_LOOP_MAX MSR_MAX_STATE_N
#endif

#if MSR_FIXED_CORE_N > 0
#define MSR_GENERIC_SPATIAL_LOOP_MIN MSR_FIXED_CORE_N
#define MSR_GENERIC_SPATIAL_LOOP_MAX MSR_FIXED_CORE_N
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MIN (MSR_FIXED_CORE_N - 1)
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MAX (MSR_FIXED_CORE_N - 1)
#elif MSR_FIXED_BOP_NX > 0
#define MSR_GENERIC_SPATIAL_LOOP_MIN MSR_FIXED_BOP_NX
#define MSR_GENERIC_SPATIAL_LOOP_MAX MSR_FIXED_BOP_NX
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MIN (MSR_FIXED_BOP_NX - 1)
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MAX (MSR_FIXED_BOP_NX - 1)
#else
#define MSR_GENERIC_SPATIAL_LOOP_MIN 1
#define MSR_GENERIC_SPATIAL_LOOP_MAX MSR_MAX_STATE_N
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MIN 0
#define MSR_GENERIC_SPATIAL_MINUS_ONE_LOOP_MAX (MSR_MAX_STATE_N - 1)
#endif

#if MSR_FIXED_HARDWARE_SUBSTEPS > 0
#define MSR_SUBSTEP_LOOP_MIN MSR_FIXED_HARDWARE_SUBSTEPS
#define MSR_SUBSTEP_LOOP_MAX MSR_FIXED_HARDWARE_SUBSTEPS
#else
#define MSR_SUBSTEP_LOOP_MIN 1
#define MSR_SUBSTEP_LOOP_MAX MSR_MAX_HARDWARE_SUBSTEPS
#endif

constexpr int kEnergyGroups = 2;
constexpr int kPrecursorGroups = 6;
constexpr int kMaxN = MSR_MAX_STATE_N;
constexpr int kMaxDelaySlots = 32;
constexpr int kMaxLoopHistory = 64;
constexpr int kCrossSectionLaneFactor = MSR_CROSS_SECTION_LANE_FACTOR;
constexpr int kNeutronicsLaneFactor = MSR_NEUTRONICS_LANE_FACTOR;
constexpr int kThermalLaneFactor = MSR_THERMAL_LANE_FACTOR;
constexpr int kHeatExchangerLaneFactor = MSR_HEAT_EXCHANGER_LANE_FACTOR;
constexpr int kReductionAccumulatorSlots = 8;
constexpr int kBatchBenchStepCount = MSR_BATCH_BENCH_STEP_COUNT;
constexpr int kBatchBenchScenarioCount = MSR_BATCH_BENCH_SCENARIO_COUNT;

static_assert(kBatchBenchStepCount > 0, "MSR_BATCH_BENCH_STEP_COUNT must be > 0");
static_assert(kBatchBenchScenarioCount > 0, "MSR_BATCH_BENCH_SCENARIO_COUNT must be > 0");
static_assert(kBatchBenchStepCount <= MSR_MAX_TRANSIENT_STEPS, "batch bench steps exceed MSR_MAX_TRANSIENT_STEPS");
static_assert(
    kBatchBenchScenarioCount <= MSR_MAX_BATCH_SCENARIOS,
    "batch bench scenarios exceed MSR_MAX_BATCH_SCENARIOS"
);

#if MSR_RESIDENT_THERMAL_FLOAT
using ResidentThermal = float;
#else
using ResidentThermal = double;
#endif

#if MSR_RESIDENT_HISTORY_FLOAT
using ResidentHistory = float;
#else
using ResidentHistory = double;
#endif

#if MSR_BATCH_CONTROL_FLOAT
using ResidentControl = float;
#else
using ResidentControl = double;
#endif

enum InletMode : int {
    kInletRecirculate = 0,
    kInletFresh = 1,
    kInletCopy = 2,
};

enum CoreInletMode : int {
    kCoreInletPrescribed = 0,
    kCoreInletHxCoupled = 1,
};

enum ExternalReactivityMode : int {
    kExternalReactivityFissionSource = 0,
    kExternalReactivityAbsorption = 1,
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
    double kinetics_amplitude;
    double kinetics_precursors[kPrecursorGroups];
    double kinetics_beta_effective[kPrecursorGroups];
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

struct ResidentDelayLine {
    ResidentHistory data[kMaxDelaySlots];
    int head;
    int size;
    int delay_steps;
};

struct ResidentDelayBundle {
    ResidentDelayLine hx_c;
    ResidentDelayLine c_hx;
    ResidentDelayLine r_hx;
    ResidentDelayLine hx_r;
    ResidentDelayLine r_pp;
    ResidentDelayLine pp_r;
};

struct ResidentPrecursorHistory {
    ResidentHistory outlet_history[kPrecursorGroups][kMaxLoopHistory];
    double last_outlet[kPrecursorGroups];
    int write_index;
    int valid_count;
};

struct ResidentStepState {
    double phi1[kMaxN];
    double phi2[kMaxN];
    double C[kPrecursorGroups][kMaxN];
    double kinetics_amplitude;
    double kinetics_precursors[kPrecursorGroups];
    double kinetics_beta_effective[kPrecursorGroups];
    ResidentThermal fuel[kMaxN];
    ResidentThermal graphite[kMaxN];
    ResidentThermal hx1_hot[kMaxN];
    ResidentThermal hx1_cold[kMaxN];
    ResidentThermal hx2_hot[kMaxN];
    ResidentThermal hx2_cold[kMaxN];
    ResidentThermal Ts_HX1_0;
    ResidentThermal Tss_HX2_0;
    ResidentThermal Tsss_pp_0;
    ResidentPrecursorHistory precursor_history;
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
    int point_kinetics_enabled;
    int external_reactivity_mode;

    int precursor_delay_older;
    int precursor_delay_newer;
    double precursor_interp_newer;

    double dz;
    double outer_dt;
    double u_core;
    double u_precursor;
    double power_scale;
    double Beta;
    double critical_fission_scale;
    double prompt_generation_time_s;
    double external_reactivity;
    double brayton_available_heat_W;

    double beta[kPrecursorGroups];
    double lambda_i[kPrecursorGroups];
    double kinetics_beta_effective[kPrecursorGroups];
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
    double brayton_compressor_temp_scale;
    double brayton_turbine_temp_scale;
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

template <typename T>
inline double as_double(T value) {
#pragma HLS INLINE
    return static_cast<double>(value);
}

template <typename DstT, typename SrcT>
inline DstT cast_scalar(SrcT value) {
#pragma HLS INLINE
    return static_cast<DstT>(value);
}

template <typename DstT, typename SrcT>
void copy_vector_cast(int n, const SrcT* src, DstT* dst) {
#pragma HLS INLINE
    for (int idx = 0; idx < n; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_GENERIC_SPATIAL_LOOP_MIN, MSR_GENERIC_SPATIAL_LOOP_MAX)
#pragma HLS PIPELINE II=1
        dst[idx] = cast_scalar<DstT>(src[idx]);
    }
}

void copy_resident_precursor_history(
    const PrecursorHistory& src,
    ResidentPrecursorHistory& dst
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    for (int group = 0; group < kPrecursorGroups; ++group) {
#if MSR_SHARED_FPU_MODE
#pragma HLS LOOP_FLATTEN off
#endif
        for (int idx = 0; idx < kMaxLoopHistory; ++idx) {
#pragma HLS PIPELINE II=1
            dst.outlet_history[group][idx] = cast_scalar<ResidentHistory>(src.outlet_history[group][idx]);
        }
        dst.last_outlet[group] = src.last_outlet[group];
    }
    dst.write_index = src.write_index;
    dst.valid_count = src.valid_count;
}

void copy_precursor_history_from_resident(
    const ResidentPrecursorHistory& src,
    PrecursorHistory& dst
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    for (int group = 0; group < kPrecursorGroups; ++group) {
#if MSR_SHARED_FPU_MODE
#pragma HLS LOOP_FLATTEN off
#endif
        for (int idx = 0; idx < kMaxLoopHistory; ++idx) {
#pragma HLS PIPELINE II=1
            dst.outlet_history[group][idx] = as_double(src.outlet_history[group][idx]);
        }
        dst.last_outlet[group] = src.last_outlet[group];
    }
    dst.write_index = src.write_index;
    dst.valid_count = src.valid_count;
}

void copy_resident_delay_line(const DelayLine& src, ResidentDelayLine& dst) {
#pragma HLS INLINE
    for (int idx = 0; idx < kMaxDelaySlots; ++idx) {
#pragma HLS PIPELINE II=1
        dst.data[idx] = cast_scalar<ResidentHistory>(src.data[idx]);
    }
    dst.head = src.head;
    dst.size = src.size;
    dst.delay_steps = src.delay_steps;
}

void copy_delay_line_from_resident(const ResidentDelayLine& src, DelayLine& dst) {
#pragma HLS INLINE
    for (int idx = 0; idx < kMaxDelaySlots; ++idx) {
#pragma HLS PIPELINE II=1
        dst.data[idx] = as_double(src.data[idx]);
    }
    dst.head = src.head;
    dst.size = src.size;
    dst.delay_steps = src.delay_steps;
}

void load_resident_state(int core_n, int bop_n, const StepState& src, ResidentStepState& dst) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    copy_vector_cast(core_n, src.phi1, dst.phi1);
    copy_vector_cast(core_n, src.phi2, dst.phi2);
    for (int group = 0; group < kPrecursorGroups; ++group) {
#if MSR_SHARED_FPU_MODE
#pragma HLS LOOP_FLATTEN off
#endif
#if !MSR_SHARED_FPU_MODE
#pragma HLS UNROLL
#endif
        copy_vector_cast(core_n, src.C[group], dst.C[group]);
    }
    dst.kinetics_amplitude = src.kinetics_amplitude;
    copy_vector_cast(kPrecursorGroups, src.kinetics_precursors, dst.kinetics_precursors);
    copy_vector_cast(kPrecursorGroups, src.kinetics_beta_effective, dst.kinetics_beta_effective);
    copy_vector_cast(core_n, src.fuel, dst.fuel);
    copy_vector_cast(core_n, src.graphite, dst.graphite);
    copy_vector_cast(bop_n, src.hx1_hot, dst.hx1_hot);
    copy_vector_cast(bop_n, src.hx1_cold, dst.hx1_cold);
    copy_vector_cast(bop_n, src.hx2_hot, dst.hx2_hot);
    copy_vector_cast(bop_n, src.hx2_cold, dst.hx2_cold);
    dst.Ts_HX1_0 = cast_scalar<ResidentThermal>(src.Ts_HX1_0);
    dst.Tss_HX2_0 = cast_scalar<ResidentThermal>(src.Tss_HX2_0);
    dst.Tsss_pp_0 = cast_scalar<ResidentThermal>(src.Tsss_pp_0);
    copy_resident_precursor_history(src.precursor_history, dst.precursor_history);
}

void store_resident_state(int core_n, int bop_n, const ResidentStepState& src, StepState& dst) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    copy_vector_cast(core_n, src.phi1, dst.phi1);
    copy_vector_cast(core_n, src.phi2, dst.phi2);
    for (int group = 0; group < kPrecursorGroups; ++group) {
#if MSR_SHARED_FPU_MODE
#pragma HLS LOOP_FLATTEN off
#endif
#if !MSR_SHARED_FPU_MODE
#pragma HLS UNROLL
#endif
        copy_vector_cast(core_n, src.C[group], dst.C[group]);
    }
    dst.kinetics_amplitude = src.kinetics_amplitude;
    copy_vector_cast(kPrecursorGroups, src.kinetics_precursors, dst.kinetics_precursors);
    copy_vector_cast(kPrecursorGroups, src.kinetics_beta_effective, dst.kinetics_beta_effective);
    copy_vector_cast(core_n, src.fuel, dst.fuel);
    copy_vector_cast(core_n, src.graphite, dst.graphite);
    copy_vector_cast(bop_n, src.hx1_hot, dst.hx1_hot);
    copy_vector_cast(bop_n, src.hx1_cold, dst.hx1_cold);
    copy_vector_cast(bop_n, src.hx2_hot, dst.hx2_hot);
    copy_vector_cast(bop_n, src.hx2_cold, dst.hx2_cold);
    dst.Ts_HX1_0 = as_double(src.Ts_HX1_0);
    dst.Tss_HX2_0 = as_double(src.Tss_HX2_0);
    dst.Tsss_pp_0 = as_double(src.Tsss_pp_0);
    copy_precursor_history_from_resident(src.precursor_history, dst.precursor_history);
}

void load_resident_delays(const DelayBundle& src, ResidentDelayBundle& dst) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    copy_resident_delay_line(src.hx_c, dst.hx_c);
    copy_resident_delay_line(src.c_hx, dst.c_hx);
    copy_resident_delay_line(src.r_hx, dst.r_hx);
    copy_resident_delay_line(src.hx_r, dst.hx_r);
    copy_resident_delay_line(src.r_pp, dst.r_pp);
    copy_resident_delay_line(src.pp_r, dst.pp_r);
}

void store_resident_delays(const ResidentDelayBundle& src, DelayBundle& dst) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#else
#pragma HLS INLINE
#endif
    copy_delay_line_from_resident(src.hx_c, dst.hx_c);
    copy_delay_line_from_resident(src.c_hx, dst.c_hx);
    copy_delay_line_from_resident(src.r_hx, dst.r_hx);
    copy_delay_line_from_resident(src.hx_r, dst.hx_r);
    copy_delay_line_from_resident(src.r_pp, dst.r_pp);
    copy_delay_line_from_resident(src.pp_r, dst.pp_r);
}

void prefetch_batch_controls(
    const double* rod_positions,
    const double* external_reactivities,
    int control_base,
    int step_count,
    ResidentControl local_rod_positions[MSR_MAX_TRANSIENT_STEPS],
    ResidentControl local_external_reactivities[MSR_MAX_TRANSIENT_STEPS]
) {
#pragma HLS INLINE
    for (int step = 0; step < step_count; ++step) {
MSR_HLS_LOOP_TRIPCOUNT(1, MSR_MAX_TRANSIENT_STEPS)
#pragma HLS PIPELINE II=1
        const int control_index = control_base + step;
        local_rod_positions[step] = cast_scalar<ResidentControl>(rod_positions[control_index]);
        local_external_reactivities[step] = cast_scalar<ResidentControl>(external_reactivities[control_index]);
    }
}

double trapz_uniform(const double* y, const double* x, int N) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
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
MSR_HLS_LOOP_TRIPCOUNT(MSR_GENERIC_SPATIAL_LOOP_MIN, MSR_GENERIC_SPATIAL_LOOP_MAX)
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

template <typename DelayLineT>
double delay_line_update(DelayLineT& line, double input_value, double initial_output, int step) {
    (void)step;
    if (line.delay_steps <= 0) {
        return input_value;
    }

    if (line.size < line.delay_steps) {
        const int tail = wrap_index(line.head + line.size, kMaxDelaySlots);
        line.data[tail] = input_value;
        ++line.size;
        return initial_output;
    }

    const double output_value = as_double(line.data[line.head]);
    line.head = wrap_index(line.head + 1, kMaxDelaySlots);
    --line.size;

    const int tail = wrap_index(line.head + line.size, kMaxDelaySlots);
    line.data[tail] = input_value;
    ++line.size;
    return output_value;
}

template <typename HistoryT>
double sample_precursor_history(const HistoryT& history, int group, int steps_old) {
    if (history.valid_count <= 0) {
        return history.last_outlet[group];
    }
    const int available = history.valid_count - 1;
    const int bounded_steps = steps_old > available ? available : steps_old;
    const int latest_index = wrap_index(history.write_index - 1, kMaxLoopHistory);
    const int sample_index = wrap_index(latest_index - bounded_steps, kMaxLoopHistory);
    return as_double(history.outlet_history[group][sample_index]);
}

double fission_source_scale(
    const KernelParams& params,
    double external_reactivity
) {
    if (params.external_reactivity_mode == kExternalReactivityAbsorption) {
        return params.critical_fission_scale;
    }
    return params.critical_fission_scale / max2(1.0 - external_reactivity, 1.0e-12);
}

template <typename HistoryT>
void record_precursor_history(HistoryT& history, const double outlet[kPrecursorGroups]) {
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

template <typename HistoryT>
void precursor_inlet_from_loop(
    const KernelParams& params,
    const HistoryT& history,
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

template <typename StateT>
void cross_sections_kernel(
    const KernelParams& params,
    const StateT& state,
    double rod_position,
    double external_reactivity,
    CrossSections& xs
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    const double source_scale = fission_source_scale(params, external_reactivity);
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kCrossSectionLaneFactor
#endif
        const double delta_T_s = as_double(state.fuel[idx]) - params.T_s_ref[idx];
        const double delta_T_gr = as_double(state.graphite[idx]) - params.T_gr_ref[idx];
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
            if (external_reactivity != 0.0 && params.external_reactivity_mode == kExternalReactivityAbsorption) {
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
            const double nu_sigma_f_unscaled = clip_min(
                params.nu_sigma_f_ref[group][idx] +
                    params.a_nu_sigma_f_s[group][idx] * delta_T_s +
                    params.a_nu_sigma_f_gr[group][idx] * delta_T_gr,
                params.min_cross_section
            );
            xs.nu_sigma_f[group][idx] = nu_sigma_f_unscaled * source_scale;
            xs.sigma_f[group][idx] = nu_sigma_f_unscaled / params.nu[group];
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
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kCrossSectionLaneFactor
#endif
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
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=3
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
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
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
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

    // The precursor dimension is fully partitioned, so update all six groups
    // alongside the spatial lanes instead of sweeping group-by-group.
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
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
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=q_prime cyclic factor=kNeutronicsLaneFactor dim=1
#endif
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        const double q_vol =
            params.power_scale *
            (xs.sigma_f[0][idx] * phi1[idx] + xs.sigma_f[1][idx] * phi2[idx]);
        q_prime[idx] = params.A_f[idx] * q_vol;
    }
}

void compute_fission_source(
    const KernelParams& params,
    const CrossSections& xs,
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    double F[kMaxN]
) {
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=F cyclic factor=kNeutronicsLaneFactor dim=1
#endif
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        F[idx] = xs.nu_sigma_f[0][idx] * phi1[idx] + xs.nu_sigma_f[1][idx] * phi2[idx];
    }
}

void neutronics_flux_rhs(
    const KernelParams& params,
    const CrossSections& xs,
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    const double C[kPrecursorGroups][kMaxN],
    double dphi1[kMaxN],
    double dphi2[kMaxN]
) {
    double F[kMaxN];
    double delayed_source[kMaxN];
    double diffusion_1[kMaxN];
    double diffusion_2[kMaxN];

#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dphi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dphi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=F cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=delayed_source cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=diffusion_1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=diffusion_2 cyclic factor=kNeutronicsLaneFactor dim=1
#endif
    diffusion_term(phi1, xs.D[0], params.N, params.dz, params.d_e[0], diffusion_1);
    diffusion_term(phi2, xs.D[1], params.N, params.dz, params.d_e[1], diffusion_2);
    compute_fission_source(params, xs, phi1, phi2, F);

    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
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
}

void combine_flux_only(
    int N,
    double dt,
    double phi1[kMaxN],
    double phi2[kMaxN],
    const double k1_phi1[kMaxN],
    const double k1_phi2[kMaxN],
    const double k2_phi1[kMaxN],
    const double k2_phi2[kMaxN],
    const double k3_phi1[kMaxN],
    const double k3_phi2[kMaxN],
    const double k4_phi1[kMaxN],
    const double k4_phi2[kMaxN]
) {
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        phi1[idx] += (dt / 6.0) * (k1_phi1[idx] + 2.0 * k2_phi1[idx] + 2.0 * k3_phi1[idx] + k4_phi1[idx]);
        phi2[idx] += (dt / 6.0) * (k1_phi2[idx] + 2.0 * k2_phi2[idx] + 2.0 * k3_phi2[idx] + k4_phi2[idx]);
    }
}

void load_flux_stage(
    int N,
    double scale,
    const double phi1[kMaxN],
    const double phi2[kMaxN],
    const double dphi1[kMaxN],
    const double dphi2[kMaxN],
    double phi1_stage[kMaxN],
    double phi2_stage[kMaxN]
) {
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=phi1_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2_stage cyclic factor=kNeutronicsLaneFactor dim=1
#endif
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        phi1_stage[idx] = phi1[idx] + scale * dphi1[idx];
        phi2_stage[idx] = phi2[idx] + scale * dphi2[idx];
    }
}

void analytic_precursor_substep(
    const KernelParams& params,
    const double precursor_inlet[kPrecursorGroups],
    double dt,
    const double F_old[kMaxN],
    const double F_new[kMaxN],
    double C[kPrecursorGroups][kMaxN]
) {
    const double inv_dz = 1.0 / max2(params.dz, 1.0e-12);
    const double advection = max2(params.u_precursor * inv_dz, 0.0);

#pragma HLS ARRAY_PARTITION variable=precursor_inlet complete
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        const double coeff = params.lambda_i[group] + advection;
        const double safe_coeff = max2(coeff, 1.0e-12);
        const double decay = exp(-safe_coeff * dt);
        double upstream = precursor_inlet[group];

        for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
            const double fission_avg = 0.5 * (F_old[idx] + F_new[idx]);
            const double source = params.beta[group] * fission_avg + advection * upstream;
            const double steady = source / safe_coeff;
            const double updated = steady + (C[group][idx] - steady) * decay;
            C[group][idx] = updated;
            upstream = updated;
        }
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
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
#endif
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        phi1[idx] += (dt / 6.0) * (k1_phi1[idx] + 2.0 * k2_phi1[idx] + 2.0 * k3_phi1[idx] + k4_phi1[idx]);
        phi2[idx] += (dt / 6.0) * (k1_phi2[idx] + 2.0 * k2_phi2[idx] + 2.0 * k3_phi2[idx] + k4_phi2[idx]);
    }
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
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
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=phi1_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=phi2_stage cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=C complete dim=1
#pragma HLS ARRAY_PARTITION variable=C cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=dC complete dim=1
#pragma HLS ARRAY_PARTITION variable=dC cyclic factor=kNeutronicsLaneFactor dim=2
#pragma HLS ARRAY_PARTITION variable=C_stage complete dim=1
#pragma HLS ARRAY_PARTITION variable=C_stage cyclic factor=kNeutronicsLaneFactor dim=2
#endif
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        phi1_stage[idx] = phi1[idx] + scale * dphi1[idx];
        phi2_stage[idx] = phi2[idx] + scale * dphi2[idx];
    }
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            C_stage[group][idx] = C[group][idx] + scale * dC[group][idx];
        }
    }
}

template <typename StateT>
void scale_neutronics_state(int N, StateT& state, double factor) {
#pragma HLS ARRAY_PARTITION variable=state.phi1 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=state.phi2 cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=state.C complete dim=1
#pragma HLS ARRAY_PARTITION variable=state.C cyclic factor=kNeutronicsLaneFactor dim=2
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        state.phi1[idx] *= factor;
        state.phi2[idx] *= factor;
    }
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            state.C[group][idx] *= factor;
        }
    }
}

template <typename StateT>
double effective_beta_from_state(
    const KernelParams& params,
    const CrossSections& xs,
    const StateT& state
) {
    double fission_source[kMaxN];
    double delayed_source[kMaxN];

#pragma HLS ARRAY_PARTITION variable=fission_source cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=delayed_source cyclic factor=kNeutronicsLaneFactor dim=1
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kNeutronicsLaneFactor
#endif
        fission_source[idx] =
            xs.nu_sigma_f[0][idx] * state.phi1[idx] +
            xs.nu_sigma_f[1][idx] * state.phi2[idx];
        delayed_source[idx] = 0.0;
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            delayed_source[idx] += params.lambda_i[group] * state.C[group][idx];
        }
    }
    return trapz_uniform(delayed_source, params.z, params.N) /
        max2(trapz_uniform(fission_source, params.z, params.N), 1.0e-12);
}

template <typename StateT>
void advance_point_kinetics_kernel(
    const KernelParams& params,
    double rho,
    StateT& state
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    msr_shared::advance_point_kinetics(
        state.kinetics_beta_effective,
        params.lambda_i,
        params.prompt_generation_time_s,
        rho,
        params.outer_dt,
        &state.kinetics_amplitude,
        state.kinetics_precursors
    );
}

template <typename StateT>
void neutronics_kernel(
    const KernelParams& params,
    CrossSections& xs,
    StateT& state,
    double q_prime[kMaxN]
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    const double actual_rho = params.external_reactivity;
    const double amplitude_old =
        (params.point_kinetics_enabled != 0) ? max2(state.kinetics_amplitude, 1.0e-12) : 1.0;
    if (params.point_kinetics_enabled != 0) {
        scale_neutronics_state(params.N, state, 1.0 / amplitude_old);
    }

    double precursor_inlet[kPrecursorGroups];
#pragma HLS ARRAY_PARTITION variable=precursor_inlet complete
    precursor_inlet_from_loop(params, state.precursor_history, precursor_inlet);

    const double dt = params.outer_dt / static_cast<double>(params.hardware_substeps);
    for (int substep = 0; substep < params.hardware_substeps; ++substep) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_SUBSTEP_LOOP_MIN, MSR_SUBSTEP_LOOP_MAX)
        double k1_phi1[kMaxN], k2_phi1[kMaxN], k3_phi1[kMaxN], k4_phi1[kMaxN];
        double k1_phi2[kMaxN], k2_phi2[kMaxN], k3_phi2[kMaxN], k4_phi2[kMaxN];
#if MSR_PRECURSOR_ANALYTIC_UPDATE
        double F_old[kMaxN];
        double F_new[kMaxN];
#else
        double k1_C[kPrecursorGroups][kMaxN];
        double k2_C[kPrecursorGroups][kMaxN];
        double k3_C[kPrecursorGroups][kMaxN];
        double k4_C[kPrecursorGroups][kMaxN];
#endif
        double phi1_stage[kMaxN], phi2_stage[kMaxN];
#if !MSR_PRECURSOR_ANALYTIC_UPDATE
        double C_stage[kPrecursorGroups][kMaxN];
#endif

#if !MSR_SHARED_FPU_MODE
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
#if MSR_PRECURSOR_ANALYTIC_UPDATE
#pragma HLS ARRAY_PARTITION variable=F_old cyclic factor=kNeutronicsLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=F_new cyclic factor=kNeutronicsLaneFactor dim=1
#else
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
#endif
#endif

#if MSR_PRECURSOR_ANALYTIC_UPDATE
        compute_fission_source(params, xs, state.phi1, state.phi2, F_old);
        neutronics_flux_rhs(params, xs, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2);
        load_flux_stage(params.N, 0.5 * dt, state.phi1, state.phi2, k1_phi1, k1_phi2, phi1_stage, phi2_stage);
        neutronics_flux_rhs(params, xs, phi1_stage, phi2_stage, state.C, k2_phi1, k2_phi2);
        load_flux_stage(params.N, 0.5 * dt, state.phi1, state.phi2, k2_phi1, k2_phi2, phi1_stage, phi2_stage);
        neutronics_flux_rhs(params, xs, phi1_stage, phi2_stage, state.C, k3_phi1, k3_phi2);
        load_flux_stage(params.N, dt, state.phi1, state.phi2, k3_phi1, k3_phi2, phi1_stage, phi2_stage);
        neutronics_flux_rhs(params, xs, phi1_stage, phi2_stage, state.C, k4_phi1, k4_phi2);
        combine_flux_only(params.N, dt, state.phi1, state.phi2, k1_phi1, k1_phi2, k2_phi1, k2_phi2, k3_phi1, k3_phi2, k4_phi1, k4_phi2);
        compute_fission_source(params, xs, state.phi1, state.phi2, F_new);
        analytic_precursor_substep(params, precursor_inlet, dt, F_old, F_new, state.C);
#else
        neutronics_rhs(params, xs, precursor_inlet, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C);
        load_neutronics_stage(params.N, 0.5 * dt, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k2_phi1, k2_phi2, k2_C);
        load_neutronics_stage(params.N, 0.5 * dt, state.phi1, state.phi2, state.C, k2_phi1, k2_phi2, k2_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k3_phi1, k3_phi2, k3_C);
        load_neutronics_stage(params.N, dt, state.phi1, state.phi2, state.C, k3_phi1, k3_phi2, k3_C, phi1_stage, phi2_stage, C_stage);
        neutronics_rhs(params, xs, precursor_inlet, phi1_stage, phi2_stage, C_stage, k4_phi1, k4_phi2, k4_C);
        combine_neutronics(params.N, dt, state.phi1, state.phi2, state.C, k1_phi1, k1_phi2, k1_C, k2_phi1, k2_phi2, k2_C, k3_phi1, k3_phi2, k3_C, k4_phi1, k4_phi2, k4_C);
#endif
    }

    compute_q_prime(params, xs, state.phi1, state.phi2, q_prime);

    if (params.point_kinetics_enabled != 0) {
        const double effective_beta_total = effective_beta_from_state(params, xs, state);
        const double beta_scale = effective_beta_total / max2(params.Beta, 1.0e-12);
        for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
            state.kinetics_beta_effective[group] = params.beta[group] * beta_scale;
        }
        advance_point_kinetics_kernel(params, actual_rho, state);
        scale_neutronics_state(params.N, state, state.kinetics_amplitude);
        compute_q_prime(params, xs, state.phi1, state.phi2, q_prime);
    }

    double outlet[kPrecursorGroups];
    for (int group = 0; group < kPrecursorGroups; ++group) {
#pragma HLS UNROLL
        outlet[group] = state.C[group][params.N - 1];
    }
    record_precursor_history(state.precursor_history, outlet);
}

template <typename ThermalStorageT>
void thermal_rhs(
    const KernelParams& params,
    const double q_prime[kMaxN],
    double inlet_temperature,
    const ThermalStorageT fuel[kMaxN],
    const ThermalStorageT graphite[kMaxN],
    double dfuel[kMaxN],
    double dgraphite[kMaxN]
) {
    const double salt_capacity = params.rho_s * params.c_p_s * params.A_s;
    const double graphite_capacity = params.rho_gr * params.c_p_g * params.A_gr;
    const double heat_exchange = params.h_sgr * params.P_sgr;
    const double graphite_axial_conductivity = params.k_gr * params.A_gr;

#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=q_prime cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dfuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dgraphite cyclic factor=kThermalLaneFactor dim=1
#endif
    for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=3
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
#endif
        const double fuel_center = as_double(fuel[idx]);
        const double graphite_center = as_double(graphite[idx]);
        const double fuel_im1 = (idx == 0) ? inlet_temperature : as_double(fuel[idx - 1]);
        const double fuel_gradient = (fuel_center - fuel_im1) / params.dz;
        const double fuel_exchange = heat_exchange * (graphite_center - fuel_center);
        dfuel[idx] =
            -params.u_core * fuel_gradient +
            (params.eta_s * q_prime[idx] + fuel_exchange) / salt_capacity +
            params.err;

        double graphite_rhs =
            (params.eta_gr * q_prime[idx] - fuel_exchange) / graphite_capacity +
            params.err;
        if (params.use_graphite_axial_conduction != 0) {
            const double graphite_left = (idx == 0) ? as_double(graphite[1]) : as_double(graphite[idx - 1]);
            const double graphite_right =
                (idx + 1 == params.N) ? as_double(graphite[params.N - 2]) : as_double(graphite[idx + 1]);
            const double second_derivative =
                (idx == 0 || idx + 1 == params.N)
                    ? 2.0 * ((idx == 0 ? graphite_right : graphite_left) - graphite_center) / (params.dz * params.dz)
                    : (graphite_right - 2.0 * graphite_center + graphite_left) / (params.dz * params.dz);
            graphite_rhs += (graphite_axial_conductivity / graphite_capacity) * second_derivative;
        }
        dgraphite[idx] = graphite_rhs;
    }
    dfuel[0] = inlet_temperature - as_double(fuel[0]);
}

template <typename ThermalStorageT>
void load_thermal_stage(
    int N,
    double scale,
    const ThermalStorageT fuel[kMaxN],
    const ThermalStorageT graphite[kMaxN],
    const double dfuel[kMaxN],
    const double dgraphite[kMaxN],
    double fuel_stage[kMaxN],
    double graphite_stage[kMaxN]
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=fuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dfuel cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dgraphite cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=fuel_stage cyclic factor=kThermalLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=graphite_stage cyclic factor=kThermalLaneFactor dim=1
#endif
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
#endif
        fuel_stage[idx] = as_double(fuel[idx]) + scale * dfuel[idx];
        graphite_stage[idx] = as_double(graphite[idx]) + scale * dgraphite[idx];
    }
}

template <typename StateT>
void thermal_kernel(
    const KernelParams& params,
    const double q_prime[kMaxN],
    double Ts_core_inlet,
    StateT& state
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    const double dt = params.outer_dt / static_cast<double>(params.hardware_substeps);
    for (int substep = 0; substep < params.hardware_substeps; ++substep) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_SUBSTEP_LOOP_MIN, MSR_SUBSTEP_LOOP_MAX)
        double k1_fuel[kMaxN], k2_fuel[kMaxN], k3_fuel[kMaxN], k4_fuel[kMaxN];
        double k1_graphite[kMaxN], k2_graphite[kMaxN], k3_graphite[kMaxN], k4_graphite[kMaxN];
        double fuel_stage[kMaxN], graphite_stage[kMaxN];

#if !MSR_SHARED_FPU_MODE
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
#endif
        thermal_rhs(params, q_prime, Ts_core_inlet, state.fuel, state.graphite, k1_fuel, k1_graphite);
        load_thermal_stage(params.N, 0.5 * dt, state.fuel, state.graphite, k1_fuel, k1_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k2_fuel, k2_graphite);
        load_thermal_stage(params.N, 0.5 * dt, state.fuel, state.graphite, k2_fuel, k2_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k3_fuel, k3_graphite);
        load_thermal_stage(params.N, dt, state.fuel, state.graphite, k3_fuel, k3_graphite, fuel_stage, graphite_stage);
        thermal_rhs(params, q_prime, Ts_core_inlet, fuel_stage, graphite_stage, k4_fuel, k4_graphite);

        for (int idx = 0; idx < params.N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_CORE_SPATIAL_LOOP_MIN, MSR_CORE_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kThermalLaneFactor
#endif
            state.fuel[idx] =
                as_double(state.fuel[idx]) +
                (dt / 6.0) * (k1_fuel[idx] + 2.0 * k2_fuel[idx] + 2.0 * k3_fuel[idx] + k4_fuel[idx]);
            state.graphite[idx] =
                as_double(state.graphite[idx]) +
                (dt / 6.0) * (k1_graphite[idx] + 2.0 * k2_graphite[idx] + 2.0 * k3_graphite[idx] + k4_graphite[idx]);
        }
        state.fuel[0] = Ts_core_inlet;
    }
}

template <typename StorageT>
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
    const StorageT hot[kMaxN],
    const StorageT cold[kMaxN],
    double dhot[kMaxN],
    double dcold[kMaxN]
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
#if !MSR_SHARED_FPU_MODE
#pragma HLS ARRAY_PARTITION variable=hot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=cold cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dhot cyclic factor=kHeatExchangerLaneFactor dim=1
#pragma HLS ARRAY_PARTITION variable=dcold cyclic factor=kHeatExchangerLaneFactor dim=1
#endif
    for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_BOP_SPATIAL_LOOP_MIN, MSR_BOP_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=3
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
#endif
        const double hot_center = as_double(hot[idx]);
        const double cold_center = as_double(cold[idx]);
        const double hot_gradient = (hot_velocity >= 0.0)
            ? ((idx == 0) ? (hot_center - hot_inlet) / dx : (hot_center - as_double(hot[idx - 1])) / dx)
            : ((idx + 1 == N) ? (hot_inlet - hot_center) / dx : (as_double(hot[idx + 1]) - hot_center) / dx);
        const double cold_gradient = (cold_velocity >= 0.0)
            ? ((idx == 0) ? (cold_center - cold_inlet) / dx : (cold_center - as_double(cold[idx - 1])) / dx)
            : ((idx + 1 == N) ? (cold_inlet - cold_center) / dx : (as_double(cold[idx + 1]) - cold_center) / dx);
        const double delta_t = hot_center - cold_center;
        dhot[idx] = -hot_velocity * hot_gradient - hot_exchange_coeff * delta_t + err;
        dcold[idx] = -cold_velocity * cold_gradient + cold_exchange_coeff * delta_t + err;
    }
}

template <typename StorageT>
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
    StorageT hot[kMaxN],
    StorageT cold[kMaxN]
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    const double dt = outer_dt / static_cast<double>(hardware_substeps);
    for (int substep = 0; substep < hardware_substeps; ++substep) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_SUBSTEP_LOOP_MIN, MSR_SUBSTEP_LOOP_MAX)
        double k1_hot[kMaxN], k2_hot[kMaxN], k3_hot[kMaxN], k4_hot[kMaxN];
        double k1_cold[kMaxN], k2_cold[kMaxN], k3_cold[kMaxN], k4_cold[kMaxN];
        double hot_stage[kMaxN], cold_stage[kMaxN];

#if !MSR_SHARED_FPU_MODE
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
#endif
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot, cold, k1_hot, k1_cold);
        for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_BOP_SPATIAL_LOOP_MIN, MSR_BOP_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
#endif
            hot_stage[idx] = hot[idx] + 0.5 * dt * k1_hot[idx];
            cold_stage[idx] = cold[idx] + 0.5 * dt * k1_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k2_hot, k2_cold);
        for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_BOP_SPATIAL_LOOP_MIN, MSR_BOP_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
#endif
            hot_stage[idx] = hot[idx] + 0.5 * dt * k2_hot[idx];
            cold_stage[idx] = cold[idx] + 0.5 * dt * k2_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k3_hot, k3_cold);
        for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_BOP_SPATIAL_LOOP_MIN, MSR_BOP_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
#endif
            hot_stage[idx] = hot[idx] + dt * k3_hot[idx];
            cold_stage[idx] = cold[idx] + dt * k3_cold[idx];
        }
        hx_rhs(N, dx, hot_velocity, cold_velocity, hot_exchange_coeff, cold_exchange_coeff, err, hot_inlet, cold_inlet, hot_stage, cold_stage, k4_hot, k4_cold);

        for (int idx = 0; idx < N; ++idx) {
MSR_HLS_LOOP_TRIPCOUNT(MSR_BOP_SPATIAL_LOOP_MIN, MSR_BOP_SPATIAL_LOOP_MAX)
#if MSR_SHARED_FPU_MODE
#pragma HLS PIPELINE II=2
#else
#pragma HLS PIPELINE II=1
#pragma HLS UNROLL factor=kHeatExchangerLaneFactor
#endif
            hot[idx] =
                as_double(hot[idx]) +
                (dt / 6.0) * (k1_hot[idx] + 2.0 * k2_hot[idx] + 2.0 * k3_hot[idx] + k4_hot[idx]);
            cold[idx] =
                as_double(cold[idx]) +
                (dt / 6.0) * (k1_cold[idx] + 2.0 * k2_cold[idx] + 2.0 * k3_cold[idx] + k4_cold[idx]);
        }
    }
}

double brayton_kernel(const KernelParams& params, double heater_outlet) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    const double T1 = params.brayton_cooler_outlet_temp;
    const double T3 = max2(heater_outlet, T1 + 5.0);
    const double T2s = T1 * params.brayton_compressor_temp_scale;
    const double T2 = T1 + (T2s - T1) / params.brayton_eta_c;
    const double T4s = T3 * params.brayton_turbine_temp_scale;
    const double T4 = T3 - params.brayton_eta_t * (T3 - T4s);
    const double requested_recuperation = params.brayton_recuperator_efficiency * max2(T4 - T2, 0.0);
    const double approach_limit = max2(T3 - params.brayton_min_heater_approach - T2, 0.0);
    const double delta_recuperation = requested_recuperation < approach_limit ? requested_recuperation : approach_limit;
    const double T2r = T2 + delta_recuperation;
    const double heater_duty_per_kg = params.c_p_sss * max2(T3 - T2r, 0.0);
    double mass_flow = params.brayton_mdot;
    if (heater_duty_per_kg > 0.0) {
        mass_flow = params.brayton_available_heat_W / heater_duty_per_kg;
        if (mass_flow > params.brayton_mdot) {
            mass_flow = params.brayton_mdot;
        }
        if (mass_flow < 0.0) {
            mass_flow = 0.0;
        }
    }
    (void)mass_flow;
    return T2r;
}

template <typename StateT, typename DelayBundleT>
void advance_coupled_step(
    StateT& local_state,
    DelayBundleT& local_delays,
    KernelParams& local_params,
    StepDiagnostics& local_diagnostics,
    int step,
    double rod_position,
    double actual_rho
) {
#if MSR_SHARED_FPU_MODE
#pragma HLS INLINE off
#endif
    CrossSections xs;
    double q_prime[kMaxN];

#if !MSR_SHARED_FPU_MODE
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
#endif

    local_params.external_reactivity = actual_rho;
    const double xs_external_rho = (local_params.point_kinetics_enabled != 0) ? 0.0 : actual_rho;
    cross_sections_kernel(local_params, local_state, rod_position, xs_external_rho, xs);
    neutronics_kernel(local_params, xs, local_state, q_prime);

    const double Ts_core_inlet = (local_params.core_inlet_mode == kCoreInletHxCoupled)
        ? delay_line_update(local_delays.hx_c, as_double(local_state.Ts_HX1_0), local_params.Ts_in, step)
        : local_params.Ts_in;
    thermal_kernel(local_params, q_prime, Ts_core_inlet, local_state);
    const double Ts_core_outlet = as_double(local_state.fuel[local_params.N - 1]);
    const double power = trapz_uniform(q_prime, local_params.z, local_params.N);
    local_params.brayton_available_heat_W = power;

    const double Ts_HX1_L = delay_line_update(local_delays.c_hx, Ts_core_outlet, local_params.Ts_out, step);
    const double Tss_HX1_0 = delay_line_update(local_delays.r_hx, as_double(local_state.Tss_HX2_0), local_params.Tss_in, step);
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
    const double Tss_HX1_L = as_double(local_state.hx1_cold[local_params.Nx - 1]);

    const double Tss_HX2_L = delay_line_update(local_delays.hx_r, Tss_HX1_L, local_params.Tss_out, step);
    const double Tsss_HX2_0 = delay_line_update(local_delays.pp_r, as_double(local_state.Tsss_pp_0), local_params.Tsss_in, step);
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
    const double Tsss_HX2_L = as_double(local_state.hx2_cold[local_params.Nx - 1]);

    const double Tsss_pp_L = delay_line_update(local_delays.r_pp, Tsss_HX2_L, local_params.Tsss_out, step);
    local_state.Tsss_pp_0 = brayton_kernel(local_params, Tsss_pp_L);

    const double phi_mid = local_state.phi1[local_params.N / 2] + local_state.phi2[local_params.N / 2];

    local_diagnostics.phi_mid = phi_mid;
    local_diagnostics.rho = actual_rho;
    local_diagnostics.power = power;
    local_diagnostics.fuel_mid = as_double(local_state.fuel[local_params.N / 2]);
    local_diagnostics.graphite_mid = as_double(local_state.graphite[local_params.N / 2]);
    local_diagnostics.core_inlet = Ts_core_inlet;
    local_diagnostics.core_outlet = Ts_core_outlet;
    local_diagnostics.hx1_hot_outlet = as_double(local_state.Ts_HX1_0);
    local_diagnostics.hx1_cold_outlet = Tss_HX1_L;
    local_diagnostics.hx2_hot_outlet = as_double(local_state.Tss_HX2_0);
    local_diagnostics.hx2_cold_outlet = Tsss_HX2_L;
    local_diagnostics.brayton_return = as_double(local_state.Tsss_pp_0);
}

template <int FixedStepCount, int FixedScenarioCount>
void run_transient_batch(
    StepState* states,
    DelayBundle* delays,
    const KernelParams* params,
    const double* rod_positions,
    const double* external_reactivities,
    StepDiagnostics* final_diagnostics,
    int runtime_step_count,
    int runtime_scenario_count
) {
    const int step_count = (FixedStepCount > 0) ? FixedStepCount : runtime_step_count;
    const int scenario_count = (FixedScenarioCount > 0) ? FixedScenarioCount : runtime_scenario_count;

    if (step_count <= 0 || scenario_count <= 0) {
        return;
    }
    if (step_count > MSR_MAX_TRANSIENT_STEPS || scenario_count > MSR_MAX_BATCH_SCENARIOS) {
        return;
    }

    ResidentStepState local_state{};
    ResidentDelayBundle local_delays{};
    KernelParams local_params{};
    StepDiagnostics local_diagnostics{};
    ResidentControl local_rod_positions[MSR_MAX_TRANSIENT_STEPS];
    ResidentControl local_external_reactivities[MSR_MAX_TRANSIENT_STEPS];

    for (int scenario = 0; scenario < scenario_count; ++scenario) {
MSR_HLS_LOOP_TRIPCOUNT(1, MSR_MAX_BATCH_SCENARIOS)
        local_params = params[scenario];
        load_resident_state(local_params.N, local_params.Nx, states[scenario], local_state);
        load_resident_delays(delays[scenario], local_delays);

        const int control_base = scenario * step_count;
        prefetch_batch_controls(
            rod_positions,
            external_reactivities,
            control_base,
            step_count,
            local_rod_positions,
            local_external_reactivities
        );

        for (int step = 0; step < step_count; ++step) {
MSR_HLS_LOOP_TRIPCOUNT(1, MSR_MAX_TRANSIENT_STEPS)
            advance_coupled_step(
                local_state,
                local_delays,
                local_params,
                local_diagnostics,
                step,
                as_double(local_rod_positions[step]),
                as_double(local_external_reactivities[step])
            );
        }

        store_resident_state(local_params.N, local_params.Nx, local_state, states[scenario]);
        store_resident_delays(local_delays, delays[scenario]);
        final_diagnostics[scenario] = local_diagnostics;
    }
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

    StepState local_state = *state;
    DelayBundle local_delays = *delays;
    KernelParams local_params = *params;
    StepDiagnostics local_diagnostics{};
    advance_coupled_step(
        local_state,
        local_delays,
        local_params,
        local_diagnostics,
        step,
        0.0,
        local_params.external_reactivity
    );

    *state = local_state;
    *delays = local_delays;
    *diagnostics = local_diagnostics;
}

extern "C" void msr_transient_batch_kernel(
    StepState* states,
    DelayBundle* delays,
    const KernelParams* params,
    const double* rod_positions,
    const double* external_reactivities,
    StepDiagnostics* final_diagnostics,
    int step_count,
    int scenario_count
) {
#pragma HLS INTERFACE m_axi port=states offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=delays offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=rod_positions offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=external_reactivities offset=slave bundle=gmem4
#pragma HLS INTERFACE m_axi port=final_diagnostics offset=slave bundle=gmem5
#pragma HLS INTERFACE s_axilite port=states bundle=control
#pragma HLS INTERFACE s_axilite port=delays bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=rod_positions bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivities bundle=control
#pragma HLS INTERFACE s_axilite port=final_diagnostics bundle=control
#pragma HLS INTERFACE s_axilite port=step_count bundle=control
#pragma HLS INTERFACE s_axilite port=scenario_count bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    run_transient_batch<0, 0>(
        states,
        delays,
        params,
        rod_positions,
        external_reactivities,
        final_diagnostics,
        step_count,
        scenario_count
    );
}

extern "C" void msr_transient_batch_bench_kernel(
    StepState* states,
    DelayBundle* delays,
    const KernelParams* params,
    const double* rod_positions,
    const double* external_reactivities,
    StepDiagnostics* final_diagnostics
) {
#pragma HLS INTERFACE m_axi port=states offset=slave bundle=gmem0
#pragma HLS INTERFACE m_axi port=delays offset=slave bundle=gmem1
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=gmem2
#pragma HLS INTERFACE m_axi port=rod_positions offset=slave bundle=gmem3
#pragma HLS INTERFACE m_axi port=external_reactivities offset=slave bundle=gmem4
#pragma HLS INTERFACE m_axi port=final_diagnostics offset=slave bundle=gmem5
#pragma HLS INTERFACE s_axilite port=states bundle=control
#pragma HLS INTERFACE s_axilite port=delays bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=rod_positions bundle=control
#pragma HLS INTERFACE s_axilite port=external_reactivities bundle=control
#pragma HLS INTERFACE s_axilite port=final_diagnostics bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control

    run_transient_batch<kBatchBenchStepCount, kBatchBenchScenarioCount>(
        states,
        delays,
        params,
        rod_positions,
        external_reactivities,
        final_diagnostics,
        kBatchBenchStepCount,
        kBatchBenchScenarioCount
    );
}

}  // namespace msr_vitis
