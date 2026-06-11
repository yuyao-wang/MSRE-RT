#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <deque>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace msr {

constexpr int kEnergyGroups = 2;
constexpr int kPrecursorGroups = 6;

struct PowerPlantState {
    int step = -1;
    double T1 = 0.0;
    double T2 = 0.0;
    double T2r = 0.0;
    double T3 = 0.0;
    double T4 = 0.0;
    double T4r = 0.0;
    double W_c = 0.0;
    double W_t = 0.0;
    double W_net = 0.0;
    double Q_in = 0.0;
    double Q_out = 0.0;
    double eta_b = 0.0;
};

struct PrecursorLoopState {
    std::deque<double> times;
    std::deque<std::array<double, kPrecursorGroups>> outlets;
    std::array<double, kPrecursorGroups> last_outlet{};
};

struct CrossSections {
    std::array<std::vector<double>, kEnergyGroups> D;
    std::array<std::vector<double>, kEnergyGroups> sigma_a;
    std::vector<double> sigma_s12;
    std::array<std::vector<double>, kEnergyGroups> nu_sigma_f;
    std::array<std::vector<double>, kEnergyGroups> sigma_f;
    std::array<std::vector<double>, kEnergyGroups> sigma_r;
};

struct HeatExchangerConfig {
    double dx = 0.0;
    double hot_velocity = 0.0;
    double cold_velocity = 0.0;
    double hot_exchange_coeff = 0.0;
    double cold_exchange_coeff = 0.0;
};

struct Parameters {
    int N = 80;
    int Nx = 80;
    int neutronics_state_size = (kEnergyGroups + kPrecursorGroups) * 80;
    double L = 172.0;
    double dz = 0.0;
    double dx = 0.0;
    double outer_dt = 1.0;
    double ode_horizon = 1.0;
    double nominal_total_power = 1.0e5;

    std::vector<double> z;
    std::vector<double> A_f;

    double v_core = 0.2;
    double u_core = 0.2;
    double u_precursor = 0.2;
    std::string inlet_mode = "recirculate";
    std::string core_inlet_mode = "hx_coupled";

    std::array<double, kEnergyGroups> neutron_velocity{0.55, 0.18};
    std::array<double, kPrecursorGroups> beta{0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088};
    std::array<double, kPrecursorGroups> lambda_i{0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5};
    double Beta = 0.0;

    std::array<double, kEnergyGroups> nu{2.45, 2.45};
    std::array<double, kEnergyGroups> chi_p{1.0, 0.0};
    std::array<double, kEnergyGroups> chi_d{1.0, 0.0};
    std::array<double, kEnergyGroups> d_e{};

    std::array<std::vector<double>, kEnergyGroups> D_ref;
    std::array<std::vector<double>, kEnergyGroups> sigma_a_ref;
    std::vector<double> sigma_s12_ref;
    std::array<std::vector<double>, kEnergyGroups> sigma_f_ref;
    std::array<std::vector<double>, kEnergyGroups> nu_sigma_f_ref;
    std::array<std::vector<double>, kEnergyGroups> transverse_buckling_sq;

    std::array<std::vector<double>, kEnergyGroups> a_sigma_a_s;
    std::array<std::vector<double>, kEnergyGroups> a_sigma_a_gr;
    std::vector<double> a_sigma_s12_s;
    std::vector<double> a_sigma_s12_gr;
    std::array<std::vector<double>, kEnergyGroups> a_nu_sigma_f_s;
    std::array<std::vector<double>, kEnergyGroups> a_nu_sigma_f_gr;
    std::array<std::vector<double>, kEnergyGroups> a_D_s;
    std::array<std::vector<double>, kEnergyGroups> a_D_gr;

    std::array<std::vector<double>, kEnergyGroups> rod_shape;
    std::array<double, kEnergyGroups> rod_sigma_a_amplitude{3.0e-4, 9.0e-4};
    std::array<double, kEnergyGroups> external_reactivity_to_absorption{2.94e-3, 8.82e-3};

    std::vector<double> T_s_ref;
    std::vector<double> T_gr_ref;

    std::vector<double> phi_1_0;
    std::vector<double> phi_2_0;
    std::vector<double> phi_0;
    std::array<std::vector<double>, kPrecursorGroups> c0_groups;
    std::vector<double> c0;

    double power_scale = 1.0;
    double reference_multiplication_ratio = 1.0;

    double precursor_loop_efficiency = 0.92;
    double precursor_loop_tau = 16.73;
    PrecursorLoopState precursor_loop_state;

    double c_p_s = 2090.0;
    double c_p_g = 1757.0;
    double rho_s = 0.0;
    double rho_gr = 0.0;
    double A_s = 1.0;
    double A_gr = 1.0;
    double P_sgr = 1.0;
    double h_sgr = 0.0;
    double k_gr = 35.0;
    bool use_graphite_axial_conduction = true;

    double eta_s = 0.30;
    double eta_gr = 0.70;
    double bc_s0 = 908.0;
    double bc_sL = 936.0;
    double bc_g0 = 918.0;
    double bc_gL = 946.0;
    std::vector<double> initialS;
    std::vector<double> initialG;
    double err = 0.0;

    double L_HX = 2.0;
    double V_he_s = 75.7e-3 / 23.6;
    double V_he_ss = 53.6e-3 / 23.6;
    double U_hx = 500.0;
    double M_he_s = 342.0;
    double M_he_ss = 117.0;
    double c_p_ss = 2416.0;

    double L_HX2 = 2.0;
    double V_he2_s = 53.6e-3 / 23.6;
    double V_he2_ss = 33.6e-3 / 23.6;
    double U2_hx = 500.0;
    double M_he2_s = 117.0;
    double M_he2_ss = 100.0;
    double c_p_sss = 2416.0;

    double brayton_gamma = 1.28;
    double brayton_eta_c = 0.89;
    double brayton_eta_t = 0.91;
    double brayton_pi_c = 1.20;
    double brayton_pi_t = 1.20;
    double brayton_recuperator_efficiency = 0.95;
    double brayton_cooler_outlet_temp = 620.0;
    double brayton_min_heater_approach = 12.0;
    double brayton_mdot = 100.0;

    std::vector<double> u_init;
    std::vector<double> v_init;
    std::vector<double> u2_init;
    std::vector<double> v2_init;

    double tau_l = 16.73;
    double tau_c = 8.46;
    double tau_hx_c = 4.0;
    double tau_c_hx = 4.0;
    double tau_hx_r = 5.0;
    double tau_r_hx = 8.0;
    double tau_r_pp = 6.0;
    double tau_pp_r = 6.0;
    double Ts_in = 908.0;
    double Ts_out = 936.0;
    double Tss_in = 802.0;
    double Tss_out = 902.0;
    double Tsss_in = 792.0;
    double Tsss_out = 830.0;

    double min_diffusion = 1.0e-5;
    double min_cross_section = 1.0e-6;
    double last_global_rho = 0.0;
    PowerPlantState last_power_plant;

    int history_step_offset = 0;
    double history_time_offset_s = 0.0;
    int steady_state_steps = 180;
    bool use_steady_state_initialization = true;

    double ode_rtol = 1.0e-4;
    double ode_atol = 1.0e-6;
    double ode_h_min = 1.0e-5;
    double ode_h_max = 0.25;
    double ode_initial_h = 0.05;
    int ode_max_steps = 100000;
};

struct SimulationOutput {
    std::vector<double> time;
    std::vector<double> phi_mid;
    std::vector<double> rho;
    std::vector<double> power;
    std::vector<double> fuel_mid;
    std::vector<double> graphite_mid;
    std::vector<double> core_inlet;
    std::vector<double> core_outlet;
    std::vector<double> hx1_hot_outlet;
    std::vector<double> hx1_cold_outlet;
    std::vector<double> hx2_hot_outlet;
    std::vector<double> hx2_cold_outlet;
    std::vector<double> brayton_return;
};

std::vector<double> Linspace(double start, double stop, int count) {
    std::vector<double> values(static_cast<std::size_t>(count), start);
    if (count <= 1) {
        return values;
    }
    const double step = (stop - start) / static_cast<double>(count - 1);
    for (int idx = 0; idx < count; ++idx) {
        values[static_cast<std::size_t>(idx)] = start + step * static_cast<double>(idx);
    }
    return values;
}

double Trapz(const std::vector<double>& y, const std::vector<double>& x) {
    if (y.size() != x.size() || y.size() < 2) {
        return 0.0;
    }
    double total = 0.0;
    for (std::size_t idx = 0; idx + 1 < y.size(); ++idx) {
        total += 0.5 * (y[idx] + y[idx + 1]) * (x[idx + 1] - x[idx]);
    }
    return total;
}

double Mean(const std::vector<double>& values) {
    if (values.empty()) {
        return 0.0;
    }
    return std::accumulate(values.begin(), values.end(), 0.0) / static_cast<double>(values.size());
}

template <std::size_t N>
double Mean(const std::array<double, N>& values) {
    return std::accumulate(values.begin(), values.end(), 0.0) / static_cast<double>(N);
}

std::vector<double> FundamentalShape(const std::vector<double>& z, double dz, double length) {
    std::vector<double> shape(z.size(), 0.0);
    for (std::size_t idx = 0; idx < z.size(); ++idx) {
        const double phase = (z[idx] + 0.5 * dz) / (length + dz);
        shape[idx] = std::max(std::sin(M_PI * phase), 1.0e-3);
    }
    return shape;
}

std::array<std::vector<double>, kEnergyGroups> GroupProfile(
    const std::array<double, kEnergyGroups>& values,
    const std::vector<double>& axial_shape
) {
    std::array<std::vector<double>, kEnergyGroups> profile;
    for (int group = 0; group < kEnergyGroups; ++group) {
        profile[group].resize(axial_shape.size(), 0.0);
        for (std::size_t idx = 0; idx < axial_shape.size(); ++idx) {
            profile[group][idx] = values[group] * axial_shape[idx];
        }
    }
    return profile;
}

std::vector<double> ScaledVector(double scalar, const std::vector<double>& values) {
    std::vector<double> result(values.size(), 0.0);
    for (std::size_t idx = 0; idx < values.size(); ++idx) {
        result[idx] = scalar * values[idx];
    }
    return result;
}

PrecursorLoopState InitializePrecursorLoopState(
    const std::array<double, kPrecursorGroups>& seed_outlet,
    double outer_dt,
    double tau_loop
) {
    const int history_size = std::max(3, static_cast<int>(std::ceil(std::max(tau_loop, outer_dt) / outer_dt)) + 3);
    PrecursorLoopState state;
    state.last_outlet = seed_outlet;
    for (int idx = 0; idx < history_size; ++idx) {
        state.times.push_back(static_cast<double>(idx - history_size + 1) * outer_dt);
        state.outlets.push_back(seed_outlet);
    }
    return state;
}

std::array<double, kPrecursorGroups> InterpolateOutlet(const PrecursorLoopState& loop_state, double target_time) {
    if (target_time <= loop_state.times.front()) {
        return loop_state.outlets.front();
    }
    if (target_time >= loop_state.times.back()) {
        return loop_state.outlets.back();
    }

    auto upper = std::lower_bound(loop_state.times.begin(), loop_state.times.end(), target_time);
    const std::size_t idx = static_cast<std::size_t>(std::distance(loop_state.times.begin(), upper));
    const double t0 = loop_state.times[idx - 1];
    const double t1 = loop_state.times[idx];
    if (std::abs(t1 - t0) < 1.0e-12) {
        return loop_state.outlets[idx];
    }

    const double weight = (target_time - t0) / (t1 - t0);
    std::array<double, kPrecursorGroups> value{};
    for (int group = 0; group < kPrecursorGroups; ++group) {
        value[group] =
            (1.0 - weight) * loop_state.outlets[idx - 1][group] +
            weight * loop_state.outlets[idx][group];
    }
    return value;
}

std::array<double, kPrecursorGroups> PrecursorInletFromLoop(const Parameters& params, double current_time) {
    if (params.inlet_mode == "fresh") {
        return {};
    }
    if (params.inlet_mode == "copy") {
        return params.precursor_loop_state.last_outlet;
    }

    const auto delayed_outlet = InterpolateOutlet(params.precursor_loop_state, current_time - params.precursor_loop_tau);
    std::array<double, kPrecursorGroups> inlet{};
    for (int group = 0; group < kPrecursorGroups; ++group) {
        inlet[group] =
            params.precursor_loop_efficiency *
            delayed_outlet[group] *
            std::exp(-params.lambda_i[group] * params.precursor_loop_tau);
    }
    return inlet;
}

void RecordPrecursorOutlet(Parameters& params, double time, const std::array<double, kPrecursorGroups>& outlet) {
    params.precursor_loop_state.times.push_back(time);
    params.precursor_loop_state.outlets.push_back(outlet);
    params.precursor_loop_state.last_outlet = outlet;
}

double TransportDelay(
    double input_value,
    double time_delay,
    double initial_output,
    std::deque<double>& buffer,
    int step,
    double dt
) {
    const int delay_steps = std::max(static_cast<int>(std::llround(time_delay / std::max(dt, 1.0e-12))), 0);
    if (step < delay_steps) {
        buffer.push_back(input_value);
        return initial_output;
    }
    const double output_value = buffer.empty() ? initial_output : buffer.front();
    if (!buffer.empty()) {
        buffer.pop_front();
    }
    buffer.push_back(input_value);
    return output_value;
}

std::array<std::vector<double>, kEnergyGroups> RodAbsorptionPerturbation(
    const Parameters& params,
    double rod_position,
    double external_reactivity
) {
    std::array<std::vector<double>, kEnergyGroups> delta_sigma_a;
    for (int group = 0; group < kEnergyGroups; ++group) {
        delta_sigma_a[group].resize(static_cast<std::size_t>(params.N), 0.0);
        for (int idx = 0; idx < params.N; ++idx) {
            double delta =
                rod_position *
                params.rod_shape[group][static_cast<std::size_t>(idx)] *
                params.rod_sigma_a_amplitude[group];
            if (external_reactivity != 0.0) {
                delta +=
                    (-external_reactivity) *
                    params.rod_shape[group][static_cast<std::size_t>(idx)] *
                    params.external_reactivity_to_absorption[group];
            }
            delta_sigma_a[group][static_cast<std::size_t>(idx)] = delta;
        }
    }
    return delta_sigma_a;
}

CrossSections BuildCrossSections(
    const std::vector<double>& temperature_fuel,
    const std::vector<double>& temperature_graphite,
    const Parameters& params,
    double rod_position,
    double external_reactivity
) {
    CrossSections xs;
    const auto delta_sigma_a_rod = RodAbsorptionPerturbation(params, rod_position, external_reactivity);

    xs.sigma_s12.resize(static_cast<std::size_t>(params.N), 0.0);
    for (int group = 0; group < kEnergyGroups; ++group) {
        xs.D[group].resize(static_cast<std::size_t>(params.N), 0.0);
        xs.sigma_a[group].resize(static_cast<std::size_t>(params.N), 0.0);
        xs.nu_sigma_f[group].resize(static_cast<std::size_t>(params.N), 0.0);
        xs.sigma_f[group].resize(static_cast<std::size_t>(params.N), 0.0);
        xs.sigma_r[group].resize(static_cast<std::size_t>(params.N), 0.0);
    }

    for (int idx = 0; idx < params.N; ++idx) {
        const double delta_T_s = temperature_fuel[static_cast<std::size_t>(idx)] - params.T_s_ref[static_cast<std::size_t>(idx)];
        const double delta_T_gr = temperature_graphite[static_cast<std::size_t>(idx)] - params.T_gr_ref[static_cast<std::size_t>(idx)];
        xs.sigma_s12[static_cast<std::size_t>(idx)] = std::max(
            params.sigma_s12_ref[static_cast<std::size_t>(idx)] +
                params.a_sigma_s12_s[static_cast<std::size_t>(idx)] * delta_T_s +
                params.a_sigma_s12_gr[static_cast<std::size_t>(idx)] * delta_T_gr,
            0.0
        );

        for (int group = 0; group < kEnergyGroups; ++group) {
            xs.D[group][static_cast<std::size_t>(idx)] = std::max(
                params.D_ref[group][static_cast<std::size_t>(idx)] +
                    params.a_D_s[group][static_cast<std::size_t>(idx)] * delta_T_s +
                    params.a_D_gr[group][static_cast<std::size_t>(idx)] * delta_T_gr,
                params.min_diffusion
            );
            xs.sigma_a[group][static_cast<std::size_t>(idx)] = std::max(
                params.sigma_a_ref[group][static_cast<std::size_t>(idx)] +
                    params.a_sigma_a_s[group][static_cast<std::size_t>(idx)] * delta_T_s +
                    params.a_sigma_a_gr[group][static_cast<std::size_t>(idx)] * delta_T_gr +
                    delta_sigma_a_rod[group][static_cast<std::size_t>(idx)],
                params.min_cross_section
            );
            xs.nu_sigma_f[group][static_cast<std::size_t>(idx)] = std::max(
                params.nu_sigma_f_ref[group][static_cast<std::size_t>(idx)] +
                    params.a_nu_sigma_f_s[group][static_cast<std::size_t>(idx)] * delta_T_s +
                    params.a_nu_sigma_f_gr[group][static_cast<std::size_t>(idx)] * delta_T_gr,
                params.min_cross_section
            );
            xs.sigma_f[group][static_cast<std::size_t>(idx)] =
                xs.nu_sigma_f[group][static_cast<std::size_t>(idx)] / params.nu[group];
            xs.sigma_r[group][static_cast<std::size_t>(idx)] =
                xs.sigma_a[group][static_cast<std::size_t>(idx)] +
                xs.D[group][static_cast<std::size_t>(idx)] * params.transverse_buckling_sq[group][static_cast<std::size_t>(idx)];
        }
        xs.sigma_r[0][static_cast<std::size_t>(idx)] += xs.sigma_s12[static_cast<std::size_t>(idx)];
    }
    return xs;
}

double EstimateGlobalReactivity(const CrossSections& xs, const Parameters& params) {
    std::vector<double> production(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> absorption(static_cast<std::size_t>(params.N), 0.0);
    for (int idx = 0; idx < params.N; ++idx) {
        for (int group = 0; group < kEnergyGroups; ++group) {
            production[static_cast<std::size_t>(idx)] +=
                xs.nu_sigma_f[group][static_cast<std::size_t>(idx)] *
                (group == 0 ? params.phi_1_0[static_cast<std::size_t>(idx)] : params.phi_2_0[static_cast<std::size_t>(idx)]);
            absorption[static_cast<std::size_t>(idx)] +=
                xs.sigma_a[group][static_cast<std::size_t>(idx)] *
                (group == 0 ? params.phi_1_0[static_cast<std::size_t>(idx)] : params.phi_2_0[static_cast<std::size_t>(idx)]);
        }
    }
    const double ratio = Trapz(production, params.z) / std::max(Trapz(absorption, params.z), 1.0e-12);
    const double k_ratio = ratio / std::max(params.reference_multiplication_ratio, 1.0e-12);
    return (k_ratio - 1.0) / std::max(k_ratio, 1.0e-12);
}

using RhsFunction = std::function<void(double, const std::vector<double>&, std::vector<double>&)>;

std::vector<double> Rk4Step(const RhsFunction& rhs, double t, const std::vector<double>& y, double h) {
    const std::size_t n = y.size();
    std::vector<double> k1(n, 0.0);
    std::vector<double> k2(n, 0.0);
    std::vector<double> k3(n, 0.0);
    std::vector<double> k4(n, 0.0);
    std::vector<double> work(n, 0.0);

    rhs(t, y, k1);
    for (std::size_t idx = 0; idx < n; ++idx) {
        work[idx] = y[idx] + 0.5 * h * k1[idx];
    }

    rhs(t + 0.5 * h, work, k2);
    for (std::size_t idx = 0; idx < n; ++idx) {
        work[idx] = y[idx] + 0.5 * h * k2[idx];
    }

    rhs(t + 0.5 * h, work, k3);
    for (std::size_t idx = 0; idx < n; ++idx) {
        work[idx] = y[idx] + h * k3[idx];
    }

    rhs(t + h, work, k4);
    std::vector<double> next(y);
    for (std::size_t idx = 0; idx < n; ++idx) {
        next[idx] += (h / 6.0) * (k1[idx] + 2.0 * k2[idx] + 2.0 * k3[idx] + k4[idx]);
    }
    return next;
}

std::vector<double> AdaptiveRk4(const std::vector<double>& y0, const RhsFunction& rhs, const Parameters& params) {
    std::vector<double> y = y0;
    const double tf = params.ode_horizon;
    if (tf <= 0.0) {
        return y;
    }

    double h = std::clamp(params.ode_initial_h, params.ode_h_min, std::min(params.ode_h_max, tf));
    const double safety = 0.9;
    double t = 0.0;
    int steps = 0;

    while (t < tf && steps < params.ode_max_steps) {
        if (t + h > tf) {
            h = tf - t;
        }

        const auto y_full = Rk4Step(rhs, t, y, h);
        auto y_half = Rk4Step(rhs, t, y, 0.5 * h);
        y_half = Rk4Step(rhs, t + 0.5 * h, y_half, 0.5 * h);

        bool finite = true;
        for (std::size_t idx = 0; idx < y.size(); ++idx) {
            finite = finite && std::isfinite(y_full[idx]) && std::isfinite(y_half[idx]);
        }
        if (!finite) {
            h *= 0.5;
            if (h < params.ode_h_min) {
                throw std::runtime_error("Adaptive RK4 failed: non-finite state at minimum step.");
            }
            continue;
        }

        double err_norm = 0.0;
        for (std::size_t idx = 0; idx < y.size(); ++idx) {
            const double scale =
                params.ode_atol +
                params.ode_rtol * std::max(std::abs(y_half[idx]), std::abs(y_full[idx]));
            const double err = (y_half[idx] - y_full[idx]) / scale;
            err_norm += err * err;
        }
        err_norm = std::sqrt(err_norm / std::max<std::size_t>(1, y.size()));

        if (err_norm <= 1.0) {
            y = y_half;
            t += h;
            ++steps;
            double growth = 2.0;
            if (err_norm > 0.0) {
                growth = std::clamp(safety * std::pow(err_norm, -0.2), 1.1, 2.0);
            }
            h = std::clamp(h * growth, params.ode_h_min, params.ode_h_max);
        } else {
            const double shrink = std::max(0.2, safety * std::pow(err_norm, -0.25));
            h = std::max(params.ode_h_min, h * shrink);
            if (h <= params.ode_h_min && err_norm > 1.0) {
                throw std::runtime_error("Adaptive RK4 failed: required step below ode_h_min.");
            }
        }
    }

    if (steps >= params.ode_max_steps && t < tf) {
        throw std::runtime_error("Adaptive RK4 failed: exceeded ode_max_steps before reaching tf.");
    }

    return y;
}

std::vector<double> DiffusionTerm(
    const std::vector<double>& phi,
    const std::vector<double>& diffusion,
    double dz,
    double d_extrap
) {
    const std::size_t n = phi.size();
    std::vector<double> phi_ext(n + 2, 0.0);
    std::vector<double> diffusion_ext(n + 2, 0.0);
    phi_ext[0] = phi[1] - 2.0 * dz * phi[0] / std::max(d_extrap, 1.0e-12);
    phi_ext[n + 1] = phi[n - 2] - 2.0 * dz * phi[n - 1] / std::max(d_extrap, 1.0e-12);
    diffusion_ext[0] = diffusion[0];
    diffusion_ext[n + 1] = diffusion[n - 1];
    for (std::size_t idx = 0; idx < n; ++idx) {
        phi_ext[idx + 1] = phi[idx];
        diffusion_ext[idx + 1] = diffusion[idx];
    }

    std::vector<double> result(n, 0.0);
    for (std::size_t idx = 0; idx < n; ++idx) {
        const double d_face_right = 0.5 * (diffusion_ext[idx + 1] + diffusion_ext[idx + 2]);
        const double d_face_left = 0.5 * (diffusion_ext[idx] + diffusion_ext[idx + 1]);
        const double phi_jump_right = phi_ext[idx + 2] - phi_ext[idx + 1];
        const double phi_jump_left = phi_ext[idx + 1] - phi_ext[idx];
        result[idx] = (d_face_right * phi_jump_right - d_face_left * phi_jump_left) / (dz * dz);
    }
    return result;
}

std::vector<double> PackNeutronicsState(
    const std::vector<double>& phi_1,
    const std::vector<double>& phi_2,
    const std::array<std::vector<double>, kPrecursorGroups>& C
) {
    std::vector<double> y;
    y.reserve(phi_1.size() * (kEnergyGroups + kPrecursorGroups));
    y.insert(y.end(), phi_1.begin(), phi_1.end());
    y.insert(y.end(), phi_2.begin(), phi_2.end());
    for (const auto& group : C) {
        y.insert(y.end(), group.begin(), group.end());
    }
    return y;
}

void UnpackNeutronicsState(
    const std::vector<double>& y,
    int N,
    std::vector<double>& phi_1,
    std::vector<double>& phi_2,
    std::array<std::vector<double>, kPrecursorGroups>& C
) {
    phi_1.assign(y.begin(), y.begin() + N);
    phi_2.assign(y.begin() + N, y.begin() + 2 * N);
    for (int group = 0; group < kPrecursorGroups; ++group) {
        const auto start = y.begin() + (2 + group) * N;
        C[group].assign(start, start + N);
    }
}

std::vector<double> PackThermalState(const std::vector<double>& fuel, const std::vector<double>& graphite) {
    std::vector<double> y;
    y.reserve(fuel.size() + graphite.size());
    y.insert(y.end(), fuel.begin(), fuel.end());
    y.insert(y.end(), graphite.begin(), graphite.end());
    return y;
}

struct NeutronicsResult {
    std::vector<double> y_n;
    std::vector<double> q_prime;
};

NeutronicsResult SolveNeutronics(
    Parameters& params,
    const std::vector<double>& y_n,
    const std::vector<double>& temperature_fuel,
    const std::vector<double>& temperature_graphite,
    double rod_position,
    double external_reactivity,
    int step
) {
    const double current_time = params.history_time_offset_s + static_cast<double>(step) * params.outer_dt;
    const auto precursor_inlet = PrecursorInletFromLoop(params, current_time);
    const auto xs = BuildCrossSections(temperature_fuel, temperature_graphite, params, rod_position, external_reactivity);
    params.last_global_rho = EstimateGlobalReactivity(xs, params);

    const int N = params.N;
    const double dz = params.dz;
    const double u_precursor = params.u_precursor;

    RhsFunction rhs = [&](double /*t*/, const std::vector<double>& y, std::vector<double>& dydt) {
        dydt.assign(y.size(), 0.0);

        std::vector<double> phi_1;
        std::vector<double> phi_2;
        std::array<std::vector<double>, kPrecursorGroups> C;
        UnpackNeutronicsState(y, N, phi_1, phi_2, C);

        std::vector<double> F(static_cast<std::size_t>(N), 0.0);
        std::vector<double> delayed_source(static_cast<std::size_t>(N), 0.0);
        for (int idx = 0; idx < N; ++idx) {
            F[static_cast<std::size_t>(idx)] =
                xs.nu_sigma_f[0][static_cast<std::size_t>(idx)] * phi_1[static_cast<std::size_t>(idx)] +
                xs.nu_sigma_f[1][static_cast<std::size_t>(idx)] * phi_2[static_cast<std::size_t>(idx)];
            for (int group = 0; group < kPrecursorGroups; ++group) {
                delayed_source[static_cast<std::size_t>(idx)] +=
                    params.lambda_i[group] * C[group][static_cast<std::size_t>(idx)];
            }
        }

        const auto diffusion_1 = DiffusionTerm(phi_1, xs.D[0], dz, params.d_e[0]);
        const auto diffusion_2 = DiffusionTerm(phi_2, xs.D[1], dz, params.d_e[1]);

        for (int idx = 0; idx < N; ++idx) {
            const double rhs_1 =
                diffusion_1[static_cast<std::size_t>(idx)] -
                xs.sigma_r[0][static_cast<std::size_t>(idx)] * phi_1[static_cast<std::size_t>(idx)] +
                params.chi_p[0] * (1.0 - params.Beta) * F[static_cast<std::size_t>(idx)] +
                params.chi_d[0] * delayed_source[static_cast<std::size_t>(idx)];

            const double rhs_2 =
                diffusion_2[static_cast<std::size_t>(idx)] -
                xs.sigma_r[1][static_cast<std::size_t>(idx)] * phi_2[static_cast<std::size_t>(idx)] +
                xs.sigma_s12[static_cast<std::size_t>(idx)] * phi_1[static_cast<std::size_t>(idx)] +
                params.chi_p[1] * (1.0 - params.Beta) * F[static_cast<std::size_t>(idx)] +
                params.chi_d[1] * delayed_source[static_cast<std::size_t>(idx)];

            dydt[static_cast<std::size_t>(idx)] = params.neutron_velocity[0] * rhs_1;
            dydt[static_cast<std::size_t>(N + idx)] = params.neutron_velocity[1] * rhs_2;
        }

        for (int group = 0; group < kPrecursorGroups; ++group) {
            for (int idx = 0; idx < N; ++idx) {
                const double C_im1 = (idx == 0)
                    ? precursor_inlet[group]
                    : C[group][static_cast<std::size_t>(idx - 1)];
                const double precursor_advection =
                    u_precursor * (C[group][static_cast<std::size_t>(idx)] - C_im1) / dz;
                const double precursor_production = params.beta[group] * F[static_cast<std::size_t>(idx)];
                dydt[static_cast<std::size_t>((2 + group) * N + idx)] =
                    precursor_production -
                    params.lambda_i[group] * C[group][static_cast<std::size_t>(idx)] -
                    precursor_advection;
            }
        }
    };

    const auto y_next = AdaptiveRk4(y_n, rhs, params);

    std::vector<double> phi_1;
    std::vector<double> phi_2;
    std::array<std::vector<double>, kPrecursorGroups> C;
    UnpackNeutronicsState(y_next, N, phi_1, phi_2, C);

    std::array<double, kPrecursorGroups> outlet{};
    for (int group = 0; group < kPrecursorGroups; ++group) {
        outlet[group] = C[group].back();
    }
    RecordPrecursorOutlet(params, current_time + params.outer_dt, outlet);

    std::vector<double> q_prime(static_cast<std::size_t>(N), 0.0);
    for (int idx = 0; idx < N; ++idx) {
        const double q_vol =
            params.power_scale *
            (
                xs.sigma_f[0][static_cast<std::size_t>(idx)] * phi_1[static_cast<std::size_t>(idx)] +
                xs.sigma_f[1][static_cast<std::size_t>(idx)] * phi_2[static_cast<std::size_t>(idx)]
            );
        q_prime[static_cast<std::size_t>(idx)] =
            params.A_f[static_cast<std::size_t>(idx)] * q_vol;
    }

    return {y_next, q_prime};
}

std::vector<double> NeumannSecondDerivative(const std::vector<double>& field, double dz) {
    std::vector<double> second_derivative(field.size(), 0.0);
    if (field.size() <= 1) {
        return second_derivative;
    }

    second_derivative.front() = 2.0 * (field[1] - field[0]) / (dz * dz);
    second_derivative.back() = 2.0 * (field[field.size() - 2] - field.back()) / (dz * dz);
    for (std::size_t idx = 1; idx + 1 < field.size(); ++idx) {
        second_derivative[idx] =
            (field[idx + 1] - 2.0 * field[idx] + field[idx - 1]) / (dz * dz);
    }
    return second_derivative;
}

std::vector<double> SolveThermalHydraulics(
    const Parameters& params,
    const std::vector<double>& y_th,
    const std::vector<double>& q_prime,
    double Ts_core_inlet
) {
    const int N = params.N;
    const double dz = params.dz;
    const double salt_capacity = params.rho_s * params.c_p_s * params.A_s;
    const double graphite_capacity = params.rho_gr * params.c_p_g * params.A_gr;
    const double heat_exchange = params.h_sgr * params.P_sgr;
    const double graphite_axial_conductivity = params.k_gr * params.A_gr;
    const double inlet_temperature = Ts_core_inlet;

    RhsFunction rhs = [&](double /*t*/, const std::vector<double>& y, std::vector<double>& dydt) {
        dydt.assign(y.size(), 0.0);

        std::vector<double> fuel(y.begin(), y.begin() + N);
        std::vector<double> graphite(y.begin() + N, y.begin() + 2 * N);

        std::vector<double> fuel_gradient(static_cast<std::size_t>(N), 0.0);
        fuel_gradient.front() = (fuel.front() - inlet_temperature) / dz;
        for (int idx = 1; idx < N; ++idx) {
            fuel_gradient[static_cast<std::size_t>(idx)] =
                (fuel[static_cast<std::size_t>(idx)] - fuel[static_cast<std::size_t>(idx - 1)]) / dz;
        }
        const auto graphite_second_derivative = NeumannSecondDerivative(graphite, dz);

        for (int idx = 0; idx < N; ++idx) {
            const double fuel_exchange = heat_exchange * (graphite[static_cast<std::size_t>(idx)] - fuel[static_cast<std::size_t>(idx)]);
            dydt[static_cast<std::size_t>(idx)] =
                -params.u_core * fuel_gradient[static_cast<std::size_t>(idx)] +
                (params.eta_s * q_prime[static_cast<std::size_t>(idx)] + fuel_exchange) / salt_capacity +
                params.err;

            double graphite_rhs =
                (params.eta_gr * q_prime[static_cast<std::size_t>(idx)] - fuel_exchange) / graphite_capacity +
                params.err;
            if (params.use_graphite_axial_conduction) {
                graphite_rhs +=
                    (graphite_axial_conductivity / graphite_capacity) *
                    graphite_second_derivative[static_cast<std::size_t>(idx)];
            }
            dydt[static_cast<std::size_t>(N + idx)] = graphite_rhs;
        }
        dydt.front() = inlet_temperature - fuel.front();
    };

    auto y0 = y_th;
    y0.front() = inlet_temperature;
    return AdaptiveRk4(y0, rhs, params);
}

double UpwindGradient(double left, double center, double right, double inlet_temperature, double dx, double signed_velocity, bool is_first, bool is_last) {
    if (signed_velocity >= 0.0) {
        return is_first ? (center - inlet_temperature) / dx : (center - left) / dx;
    }
    return is_last ? (inlet_temperature - center) / dx : (right - center) / dx;
}

std::vector<double> SolveHeatExchanger(
    const Parameters& params,
    const std::vector<double>& y_hx,
    double hot_inlet,
    double cold_inlet,
    const HeatExchangerConfig& config
) {
    const int Nx = params.Nx;
    RhsFunction rhs = [&](double /*t*/, const std::vector<double>& y, std::vector<double>& dydt) {
        dydt.assign(y.size(), 0.0);
        std::vector<double> hot(y.begin(), y.begin() + Nx);
        std::vector<double> cold(y.begin() + Nx, y.begin() + 2 * Nx);

        for (int idx = 0; idx < Nx; ++idx) {
            const double hot_gradient = UpwindGradient(
                idx == 0 ? hot.front() : hot[static_cast<std::size_t>(idx - 1)],
                hot[static_cast<std::size_t>(idx)],
                idx + 1 == Nx ? hot.back() : hot[static_cast<std::size_t>(idx + 1)],
                hot_inlet,
                config.dx,
                config.hot_velocity,
                idx == 0,
                idx + 1 == Nx
            );
            const double cold_gradient = UpwindGradient(
                idx == 0 ? cold.front() : cold[static_cast<std::size_t>(idx - 1)],
                cold[static_cast<std::size_t>(idx)],
                idx + 1 == Nx ? cold.back() : cold[static_cast<std::size_t>(idx + 1)],
                cold_inlet,
                config.dx,
                config.cold_velocity,
                idx == 0,
                idx + 1 == Nx
            );
            const double delta_t =
                hot[static_cast<std::size_t>(idx)] - cold[static_cast<std::size_t>(idx)];
            dydt[static_cast<std::size_t>(idx)] =
                -config.hot_velocity * hot_gradient -
                config.hot_exchange_coeff * delta_t +
                params.err;
            dydt[static_cast<std::size_t>(Nx + idx)] =
                -config.cold_velocity * cold_gradient +
                config.cold_exchange_coeff * delta_t +
                params.err;
        }
    };

    return AdaptiveRk4(y_hx, rhs, params);
}

HeatExchangerConfig Hx1Config(const Parameters& params) {
    HeatExchangerConfig config;
    config.dx = params.L_HX / std::max(params.Nx - 1, 1);
    config.hot_velocity = -params.V_he_s;
    config.cold_velocity = params.V_he_ss;
    config.hot_exchange_coeff = params.U_hx / (params.M_he_s * params.c_p_s);
    config.cold_exchange_coeff = params.U_hx / (params.M_he_ss * params.c_p_ss);
    return config;
}

HeatExchangerConfig Hx2Config(const Parameters& params) {
    HeatExchangerConfig config;
    config.dx = params.L_HX2 / std::max(params.Nx - 1, 1);
    config.hot_velocity = -params.V_he2_s;
    config.cold_velocity = params.V_he2_ss;
    config.hot_exchange_coeff = params.U2_hx / (params.M_he2_s * params.c_p_ss);
    config.cold_exchange_coeff = params.U2_hx / (params.M_he2_ss * params.c_p_sss);
    return config;
}

double PowerPlantTemp(double heater_outlet, Parameters& params, int step) {
    const double T1 = params.brayton_cooler_outlet_temp;
    const double T3 = std::max(heater_outlet, T1 + 5.0);
    const double T2s = T1 * std::pow(params.brayton_pi_c, (params.brayton_gamma - 1.0) / params.brayton_gamma);
    const double T2 = T1 + (T2s - T1) / params.brayton_eta_c;
    const double T4s = T3 * std::pow(params.brayton_pi_t, -(params.brayton_gamma - 1.0) / params.brayton_gamma);
    const double T4 = T3 - params.brayton_eta_t * (T3 - T4s);

    const double requested_recuperation =
        params.brayton_recuperator_efficiency * std::max(T4 - T2, 0.0);
    const double approach_limit =
        std::max(T3 - params.brayton_min_heater_approach - T2, 0.0);
    const double delta_recuperation = std::min(requested_recuperation, approach_limit);

    const double T2r = T2 + delta_recuperation;
    const double T4r = T4 - delta_recuperation;
    const double mass_flow = params.brayton_mdot;
    const double cp_b = params.c_p_sss;
    const double W_c = mass_flow * cp_b * std::max(T2 - T1, 0.0);
    const double W_t = mass_flow * cp_b * std::max(T3 - T4, 0.0);
    const double W_net = W_t - W_c;
    const double Q_in = mass_flow * cp_b * std::max(T3 - T2r, 0.0);
    const double Q_out = mass_flow * cp_b * std::max(T4r - T1, 0.0);

    params.last_power_plant = {
        step,
        T1,
        T2,
        T2r,
        T3,
        T4,
        T4r,
        W_c,
        W_t,
        W_net,
        Q_in,
        Q_out,
        W_net / std::max(Q_in, 1.0e-12)
    };
    return T2r;
}

void InitializeSystemSteadyState(Parameters& params) {
    const int N = params.N;
    const int Nx = params.Nx;

    auto y_n = PackNeutronicsState(params.phi_1_0, params.phi_2_0, params.c0_groups);
    auto y_th = PackThermalState(params.initialS, params.initialG);
    auto y_hx1 = PackThermalState(params.u_init, params.v_init);
    auto y_hx2 = PackThermalState(params.u2_init, params.v2_init);

    std::vector<double> temperature_fuel = params.initialS;
    std::vector<double> temperature_graphite = params.initialG;
    std::vector<double> q_prime(static_cast<std::size_t>(N), 0.0);

    double Tss_HX2_0 = params.Tss_in;
    double Ts_HX1_0 = params.Ts_in;
    double Tsss_pp_0 = params.Tsss_in;

    std::deque<double> buffer_hx_c;
    std::deque<double> buffer_c_hx;
    std::deque<double> buffer_r_hx;
    std::deque<double> buffer_hx_r;
    std::deque<double> buffer_r_pp;
    std::deque<double> buffer_pp_r;

    for (int step = 0; step < params.steady_state_steps; ++step) {
        const auto neutronics = SolveNeutronics(
            params,
            y_n,
            temperature_fuel,
            temperature_graphite,
            0.0,
            0.0,
            step
        );
        y_n = neutronics.y_n;
        q_prime = neutronics.q_prime;

        const double Ts_core_0 = (params.core_inlet_mode == "hx_coupled")
            ? TransportDelay(Ts_HX1_0, params.tau_hx_c, params.Ts_in, buffer_hx_c, step, params.outer_dt)
            : params.Ts_in;

        y_th = SolveThermalHydraulics(params, y_th, q_prime, Ts_core_0);
        temperature_fuel.assign(y_th.begin(), y_th.begin() + N);
        temperature_graphite.assign(y_th.begin() + N, y_th.begin() + 2 * N);
        const double Ts_core_L = temperature_fuel.back();

        const double Ts_HX1_L = TransportDelay(Ts_core_L, params.tau_c_hx, params.Ts_out, buffer_c_hx, step, params.outer_dt);
        const double Tss_HX1_0 = TransportDelay(Tss_HX2_0, params.tau_r_hx, params.Tss_in, buffer_r_hx, step, params.outer_dt);
        y_hx1 = SolveHeatExchanger(params, y_hx1, Ts_HX1_L, Tss_HX1_0, Hx1Config(params));
        const std::vector<double> Ts_HX1(y_hx1.begin(), y_hx1.begin() + Nx);
        const std::vector<double> Tss_HX1(y_hx1.begin() + Nx, y_hx1.begin() + 2 * Nx);
        Ts_HX1_0 = Ts_HX1.front();
        const double Tss_HX1_L = Tss_HX1.back();

        const double Tss_HX2_L = TransportDelay(Tss_HX1_L, params.tau_hx_r, params.Tss_out, buffer_hx_r, step, params.outer_dt);
        const double Tsss_HX2_0 = TransportDelay(Tsss_pp_0, params.tau_pp_r, params.Tsss_in, buffer_pp_r, step, params.outer_dt);
        y_hx2 = SolveHeatExchanger(params, y_hx2, Tss_HX2_L, Tsss_HX2_0, Hx2Config(params));
        const std::vector<double> Tss_HX2(y_hx2.begin(), y_hx2.begin() + Nx);
        const std::vector<double> Tsss_HX2(y_hx2.begin() + Nx, y_hx2.begin() + 2 * Nx);
        Tss_HX2_0 = Tss_HX2.front();
        const double Tsss_HX2_L = Tsss_HX2.back();

        const double Tsss_pp_L = TransportDelay(Tsss_HX2_L, params.tau_r_pp, params.Tsss_out, buffer_r_pp, step, params.outer_dt);
        Tsss_pp_0 = PowerPlantTemp(Tsss_pp_L, params, step);
    }

    std::vector<double> phi_1;
    std::vector<double> phi_2;
    std::array<std::vector<double>, kPrecursorGroups> C;
    UnpackNeutronicsState(y_n, N, phi_1, phi_2, C);

    params.phi_1_0 = phi_1;
    params.phi_2_0 = phi_2;
    params.phi_0.clear();
    params.phi_0.insert(params.phi_0.end(), phi_1.begin(), phi_1.end());
    params.phi_0.insert(params.phi_0.end(), phi_2.begin(), phi_2.end());
    params.c0_groups = C;
    params.c0.clear();
    for (const auto& group : C) {
        params.c0.insert(params.c0.end(), group.begin(), group.end());
    }
    params.initialS = std::vector<double>(y_th.begin(), y_th.begin() + N);
    params.initialG = std::vector<double>(y_th.begin() + N, y_th.begin() + 2 * N);
    params.T_s_ref = params.initialS;
    params.T_gr_ref = params.initialG;
    params.u_init = std::vector<double>(y_hx1.begin(), y_hx1.begin() + Nx);
    params.v_init = std::vector<double>(y_hx1.begin() + Nx, y_hx1.begin() + 2 * Nx);
    params.u2_init = std::vector<double>(y_hx2.begin(), y_hx2.begin() + Nx);
    params.v2_init = std::vector<double>(y_hx2.begin() + Nx, y_hx2.begin() + 2 * Nx);
    params.history_step_offset = params.steady_state_steps;
    params.history_time_offset_s = static_cast<double>(params.steady_state_steps) * params.outer_dt;
}

Parameters GenerateParameters() {
    Parameters params;
    params.z = Linspace(0.0, params.L, params.N);
    params.dz = params.L / static_cast<double>(params.N - 1);
    params.Nx = params.N;
    params.dx = params.L / static_cast<double>(params.Nx - 1);
    params.neutronics_state_size = (kEnergyGroups + kPrecursorGroups) * params.N;
    params.Beta = std::accumulate(params.beta.begin(), params.beta.end(), 0.0);
    params.d_e = {2.0 * params.dz, 2.0 * params.dz};

    params.initialS.resize(static_cast<std::size_t>(params.N), 0.0);
    params.initialG.resize(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> axial_slow_taper(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> axial_fast_taper(static_cast<std::size_t>(params.N), 0.0);
    for (int idx = 0; idx < params.N; ++idx) {
        params.initialS[static_cast<std::size_t>(idx)] =
            params.bc_s0 + (params.bc_sL - params.bc_s0) * (0.2 + 0.8 * params.z[static_cast<std::size_t>(idx)] / params.L);
        params.initialG[static_cast<std::size_t>(idx)] =
            params.bc_g0 + (params.bc_gL - params.bc_g0) * (0.15 + 0.85 * params.z[static_cast<std::size_t>(idx)] / params.L);
        axial_slow_taper[static_cast<std::size_t>(idx)] =
            1.0 + 0.04 * std::cos(M_PI * params.z[static_cast<std::size_t>(idx)] / params.L);
        axial_fast_taper[static_cast<std::size_t>(idx)] =
            1.0 + 0.02 * std::sin(2.0 * M_PI * params.z[static_cast<std::size_t>(idx)] / params.L);
    }

    params.T_s_ref = params.initialS;
    params.T_gr_ref = params.initialG;

    const auto mode_shape = FundamentalShape(params.z, params.dz, params.L);

    params.D_ref[0] = ScaledVector(1.35, axial_fast_taper);
    params.D_ref[1] = ScaledVector(0.45, axial_slow_taper);
    params.sigma_s12_ref = ScaledVector(0.0120, axial_slow_taper);
    params.sigma_a_ref[0] = ScaledVector(0.0027, axial_fast_taper);
    params.sigma_a_ref[1] = ScaledVector(0.0054, axial_slow_taper);
    params.sigma_f_ref[0] = ScaledVector(6.0e-4, axial_fast_taper);
    params.sigma_f_ref[1] = ScaledVector(2.45e-3, axial_slow_taper);
    params.nu_sigma_f_ref[0].resize(static_cast<std::size_t>(params.N), 0.0);
    params.nu_sigma_f_ref[1].resize(static_cast<std::size_t>(params.N), 0.0);
    params.transverse_buckling_sq[0].assign(static_cast<std::size_t>(params.N), 0.0);
    params.transverse_buckling_sq[1].assign(static_cast<std::size_t>(params.N), 0.0);

    const auto a_sigma_a_s = GroupProfile({2.6e-6, 4.1e-6}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    const auto a_sigma_a_gr = GroupProfile({1.8e-6, 2.6e-6}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    const auto a_nu_sigma_f_s = GroupProfile({-2.4e-6, -4.3e-6}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    const auto a_nu_sigma_f_gr = GroupProfile({-1.7e-6, -2.9e-6}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    const auto a_D_s = GroupProfile({2.0e-5, 1.2e-5}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    const auto a_D_gr = GroupProfile({1.2e-5, 8.0e-6}, std::vector<double>(static_cast<std::size_t>(params.N), 1.0));
    params.a_sigma_a_s = a_sigma_a_s;
    params.a_sigma_a_gr = a_sigma_a_gr;
    params.a_nu_sigma_f_s = a_nu_sigma_f_s;
    params.a_nu_sigma_f_gr = a_nu_sigma_f_gr;
    params.a_D_s = a_D_s;
    params.a_D_gr = a_D_gr;
    params.a_sigma_s12_s.assign(static_cast<std::size_t>(params.N), -5.5e-7);
    params.a_sigma_s12_gr.assign(static_cast<std::size_t>(params.N), -3.5e-7);

    for (int idx = 0; idx < params.N; ++idx) {
        params.nu_sigma_f_ref[0][static_cast<std::size_t>(idx)] =
            params.nu[0] * params.sigma_f_ref[0][static_cast<std::size_t>(idx)];
        params.nu_sigma_f_ref[1][static_cast<std::size_t>(idx)] =
            params.nu[1] * params.sigma_f_ref[1][static_cast<std::size_t>(idx)];
    }

    for (int group = 0; group < kEnergyGroups; ++group) {
        params.rod_shape[group].resize(static_cast<std::size_t>(params.N), 0.0);
    }
    for (int idx = 0; idx < params.N; ++idx) {
        params.rod_shape[0][static_cast<std::size_t>(idx)] = std::exp(
            -std::pow(params.z[static_cast<std::size_t>(idx)] - 0.55 * params.L, 2) /
            (2.0 * std::pow(0.17 * params.L, 2))
        );
        params.rod_shape[1][static_cast<std::size_t>(idx)] = std::exp(
            -std::pow(params.z[static_cast<std::size_t>(idx)] - 0.55 * params.L, 2) /
            (2.0 * std::pow(0.16 * params.L, 2))
        );
    }
    for (int group = 0; group < kEnergyGroups; ++group) {
        const double max_value = *std::max_element(params.rod_shape[group].begin(), params.rod_shape[group].end());
        for (double& value : params.rod_shape[group]) {
            value /= std::max(max_value, 1.0e-12);
        }
    }

    params.phi_1_0 = ScaledVector(0.45, mode_shape);
    params.phi_2_0 = mode_shape;
    params.phi_0.clear();
    params.phi_0.insert(params.phi_0.end(), params.phi_1_0.begin(), params.phi_1_0.end());
    params.phi_0.insert(params.phi_0.end(), params.phi_2_0.begin(), params.phi_2_0.end());

    std::vector<double> F0(static_cast<std::size_t>(params.N), 0.0);
    for (int idx = 0; idx < params.N; ++idx) {
        F0[static_cast<std::size_t>(idx)] =
            params.nu_sigma_f_ref[0][static_cast<std::size_t>(idx)] * params.phi_1_0[static_cast<std::size_t>(idx)] +
            params.nu_sigma_f_ref[1][static_cast<std::size_t>(idx)] * params.phi_2_0[static_cast<std::size_t>(idx)];
    }
    const double precursor_reduction = 1.0 / (1.0 + (params.v_core * params.tau_l / std::max(params.L, 1.0)));
    params.c0.clear();
    for (int group = 0; group < kPrecursorGroups; ++group) {
        params.c0_groups[group].resize(static_cast<std::size_t>(params.N), 0.0);
        for (int idx = 0; idx < params.N; ++idx) {
            params.c0_groups[group][static_cast<std::size_t>(idx)] =
                params.beta[group] * F0[static_cast<std::size_t>(idx)] / params.lambda_i[group] * precursor_reduction;
            params.c0.push_back(params.c0_groups[group][static_cast<std::size_t>(idx)]);
        }
    }

    params.A_f.assign(static_cast<std::size_t>(params.N), 4094.0);
    std::vector<double> sigma_f_total_ref(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> reference_production(static_cast<std::size_t>(params.N), 0.0);
    std::vector<double> reference_absorption(static_cast<std::size_t>(params.N), 0.0);
    for (int idx = 0; idx < params.N; ++idx) {
        sigma_f_total_ref[static_cast<std::size_t>(idx)] =
            params.sigma_f_ref[0][static_cast<std::size_t>(idx)] * params.phi_1_0[static_cast<std::size_t>(idx)] +
            params.sigma_f_ref[1][static_cast<std::size_t>(idx)] * params.phi_2_0[static_cast<std::size_t>(idx)];
        reference_production[static_cast<std::size_t>(idx)] =
            params.nu_sigma_f_ref[0][static_cast<std::size_t>(idx)] * params.phi_1_0[static_cast<std::size_t>(idx)] +
            params.nu_sigma_f_ref[1][static_cast<std::size_t>(idx)] * params.phi_2_0[static_cast<std::size_t>(idx)];
        reference_absorption[static_cast<std::size_t>(idx)] =
            params.sigma_a_ref[0][static_cast<std::size_t>(idx)] * params.phi_1_0[static_cast<std::size_t>(idx)] +
            params.sigma_a_ref[1][static_cast<std::size_t>(idx)] * params.phi_2_0[static_cast<std::size_t>(idx)];
    }
    const double raw_power = Trapz([&]() {
        std::vector<double> power(static_cast<std::size_t>(params.N), 0.0);
        for (int idx = 0; idx < params.N; ++idx) {
            power[static_cast<std::size_t>(idx)] =
                params.A_f[static_cast<std::size_t>(idx)] * sigma_f_total_ref[static_cast<std::size_t>(idx)];
        }
        return power;
    }(), params.z);
    params.power_scale = params.nominal_total_power / std::max(raw_power, 1.0e-12);
    params.reference_multiplication_ratio =
        Trapz(reference_production, params.z) /
        std::max(Trapz(reference_absorption, params.z), 1.0e-12);

    std::array<double, kPrecursorGroups> seed_outlet{};
    for (int group = 0; group < kPrecursorGroups; ++group) {
        seed_outlet[group] = params.c0_groups[group].back();
    }
    params.precursor_loop_tau = params.tau_l;
    params.precursor_loop_state = InitializePrecursorLoopState(seed_outlet, params.outer_dt, params.tau_l);

    params.rho_s = 1448.0 / (params.A_s * params.L);
    params.rho_gr = 3687.0 / (params.A_gr * params.L);
    params.h_sgr = 15000.0 / (params.P_sgr * params.L);

    params.u_init = Linspace(params.bc_s0, params.bc_sL, params.N);
    params.v_init = Linspace(802.0, 902.0, params.N);
    params.u2_init = Linspace(802.0, 902.0, params.N);
    params.v2_init = Linspace(792.0, 830.0, params.N);

    params.Ts_in = params.bc_s0;
    params.Ts_out = params.bc_sL;
    params.Tss_in = 802.0;
    params.Tss_out = 902.0;
    params.Tsss_in = 792.0;
    params.Tsss_out = 830.0;

    if (params.use_steady_state_initialization) {
        InitializeSystemSteadyState(params);
    }
    return params;
}

void WriteTraceCsv(const SimulationOutput& output, const std::filesystem::path& path) {
    std::ofstream stream(path);
    stream << "time_s,phi_mid,rho,power,fuel_mid,graphite_mid,core_inlet,core_outlet,"
              "hx1_hot_outlet,hx1_cold_outlet,hx2_hot_outlet,hx2_cold_outlet,brayton_return\n";
    stream << std::setprecision(16);
    for (std::size_t idx = 0; idx < output.time.size(); ++idx) {
        stream
            << output.time[idx] << ','
            << output.phi_mid[idx] << ','
            << output.rho[idx] << ','
            << output.power[idx] << ','
            << output.fuel_mid[idx] << ','
            << output.graphite_mid[idx] << ','
            << output.core_inlet[idx] << ','
            << output.core_outlet[idx] << ','
            << output.hx1_hot_outlet[idx] << ','
            << output.hx1_cold_outlet[idx] << ','
            << output.hx2_hot_outlet[idx] << ','
            << output.hx2_cold_outlet[idx] << ','
            << output.brayton_return[idx] << '\n';
    }
}

void WriteAxialCsv(
    const std::vector<double>& z,
    const std::vector<double>& phi,
    const std::array<std::vector<double>, kPrecursorGroups>& C,
    const std::vector<double>& fuel,
    const std::vector<double>& graphite,
    const std::filesystem::path& path
) {
    std::ofstream stream(path);
    stream << "z,phi,C1,C2,C3,C4,C5,C6,fuel_temp,graphite_temp\n";
    stream << std::setprecision(16);
    for (std::size_t idx = 0; idx < z.size(); ++idx) {
        stream << z[idx] << ',' << phi[idx];
        for (int group = 0; group < kPrecursorGroups; ++group) {
            stream << ',' << C[group][idx];
        }
        stream << ',' << fuel[idx] << ',' << graphite[idx] << '\n';
    }
}

SimulationOutput RunSimulation(Parameters& params, int time_span, const std::filesystem::path& output_dir) {
    std::filesystem::create_directories(output_dir);

    auto y_n = PackNeutronicsState(params.phi_1_0, params.phi_2_0, params.c0_groups);
    auto y_th = PackThermalState(params.initialS, params.initialG);
    auto y_hx1 = PackThermalState(params.u_init, params.v_init);
    auto y_hx2 = PackThermalState(params.u2_init, params.v2_init);

    double Tss_HX2_0 = params.Tss_in;
    double Ts_HX1_0 = params.Ts_in;
    double Tsss_pp_0 = params.Tsss_in;

    std::deque<double> buffer_hx_c;
    std::deque<double> buffer_c_hx;
    std::deque<double> buffer_r_hx;
    std::deque<double> buffer_hx_r;
    std::deque<double> buffer_r_pp;
    std::deque<double> buffer_pp_r;

    std::vector<double> temperature_fuel = params.initialS;
    std::vector<double> temperature_graphite = params.initialG;
    std::vector<double> q_prime(static_cast<std::size_t>(params.N), 0.0);

    SimulationOutput output;
    output.time.resize(static_cast<std::size_t>(time_span), 0.0);
    output.phi_mid.resize(static_cast<std::size_t>(time_span), 0.0);
    output.rho.resize(static_cast<std::size_t>(time_span), 0.0);
    output.power.resize(static_cast<std::size_t>(time_span), 0.0);
    output.fuel_mid.resize(static_cast<std::size_t>(time_span), 0.0);
    output.graphite_mid.resize(static_cast<std::size_t>(time_span), 0.0);
    output.core_inlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.core_outlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.hx1_hot_outlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.hx1_cold_outlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.hx2_hot_outlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.hx2_cold_outlet.resize(static_cast<std::size_t>(time_span), 0.0);
    output.brayton_return.resize(static_cast<std::size_t>(time_span), 0.0);

    std::vector<double> phi_1;
    std::vector<double> phi_2;
    std::array<std::vector<double>, kPrecursorGroups> C;

    const int mid_idx = params.N / 2;
    for (int step = 0; step < time_span; ++step) {
        const auto neutronics = SolveNeutronics(
            params,
            y_n,
            temperature_fuel,
            temperature_graphite,
            0.0,
            0.0,
            step
        );
        y_n = neutronics.y_n;
        q_prime = neutronics.q_prime;
        UnpackNeutronicsState(y_n, params.N, phi_1, phi_2, C);

        std::vector<double> phi(static_cast<std::size_t>(params.N), 0.0);
        for (int idx = 0; idx < params.N; ++idx) {
            phi[static_cast<std::size_t>(idx)] =
                phi_1[static_cast<std::size_t>(idx)] + phi_2[static_cast<std::size_t>(idx)];
        }

        const double Ts_core_0 = (params.core_inlet_mode == "hx_coupled")
            ? TransportDelay(Ts_HX1_0, params.tau_hx_c, params.Ts_in, buffer_hx_c, step, params.outer_dt)
            : params.Ts_in;
        y_th = SolveThermalHydraulics(params, y_th, q_prime, Ts_core_0);
        temperature_fuel.assign(y_th.begin(), y_th.begin() + params.N);
        temperature_graphite.assign(y_th.begin() + params.N, y_th.begin() + 2 * params.N);
        const double Ts_core_L = temperature_fuel.back();

        const double Ts_HX1_L = TransportDelay(Ts_core_L, params.tau_c_hx, params.Ts_out, buffer_c_hx, step, params.outer_dt);
        const double Tss_HX1_0 = TransportDelay(Tss_HX2_0, params.tau_r_hx, params.Tss_in, buffer_r_hx, step, params.outer_dt);
        y_hx1 = SolveHeatExchanger(params, y_hx1, Ts_HX1_L, Tss_HX1_0, Hx1Config(params));
        const std::vector<double> Ts_HX1(y_hx1.begin(), y_hx1.begin() + params.Nx);
        const std::vector<double> Tss_HX1(y_hx1.begin() + params.Nx, y_hx1.begin() + 2 * params.Nx);
        Ts_HX1_0 = Ts_HX1.front();
        const double Tss_HX1_L = Tss_HX1.back();

        const double Tss_HX2_L = TransportDelay(Tss_HX1_L, params.tau_hx_r, params.Tss_out, buffer_hx_r, step, params.outer_dt);
        const double Tsss_HX2_0 = TransportDelay(Tsss_pp_0, params.tau_pp_r, params.Tsss_in, buffer_pp_r, step, params.outer_dt);
        y_hx2 = SolveHeatExchanger(params, y_hx2, Tss_HX2_L, Tsss_HX2_0, Hx2Config(params));
        const std::vector<double> Tss_HX2(y_hx2.begin(), y_hx2.begin() + params.Nx);
        const std::vector<double> Tsss_HX2(y_hx2.begin() + params.Nx, y_hx2.begin() + 2 * params.Nx);
        Tss_HX2_0 = Tss_HX2.front();
        const double Tsss_HX2_L = Tsss_HX2.back();

        const double Tsss_pp_L = TransportDelay(Tsss_HX2_L, params.tau_r_pp, params.Tsss_out, buffer_r_pp, step, params.outer_dt);
        Tsss_pp_0 = PowerPlantTemp(Tsss_pp_L, params, step);

        output.time[static_cast<std::size_t>(step)] = static_cast<double>(step) * params.outer_dt;
        output.phi_mid[static_cast<std::size_t>(step)] = phi[static_cast<std::size_t>(mid_idx)];
        output.rho[static_cast<std::size_t>(step)] = params.last_global_rho;
        output.power[static_cast<std::size_t>(step)] = Trapz(q_prime, params.z);
        output.fuel_mid[static_cast<std::size_t>(step)] = temperature_fuel[static_cast<std::size_t>(mid_idx)];
        output.graphite_mid[static_cast<std::size_t>(step)] = temperature_graphite[static_cast<std::size_t>(mid_idx)];
        output.core_inlet[static_cast<std::size_t>(step)] = Ts_core_0;
        output.core_outlet[static_cast<std::size_t>(step)] = Ts_core_L;
        output.hx1_hot_outlet[static_cast<std::size_t>(step)] = Ts_HX1_0;
        output.hx1_cold_outlet[static_cast<std::size_t>(step)] = Tss_HX1_L;
        output.hx2_hot_outlet[static_cast<std::size_t>(step)] = Tss_HX2_0;
        output.hx2_cold_outlet[static_cast<std::size_t>(step)] = Tsss_HX2_L;
        output.brayton_return[static_cast<std::size_t>(step)] = Tsss_pp_0;
    }

    std::vector<double> phi(static_cast<std::size_t>(params.N), 0.0);
    for (int idx = 0; idx < params.N; ++idx) {
        phi[static_cast<std::size_t>(idx)] =
            phi_1[static_cast<std::size_t>(idx)] + phi_2[static_cast<std::size_t>(idx)];
    }

    WriteTraceCsv(output, output_dir / "centerline_trace.csv");
    WriteAxialCsv(params.z, phi, C, temperature_fuel, temperature_graphite, output_dir / "axial_state.csv");
    return output;
}

}  // namespace msr

int main(int argc, char** argv) {
    int steps = 600;
    std::filesystem::path output_dir = "cpp/results";
    if (argc >= 2) {
        steps = std::stoi(argv[1]);
    }
    if (argc >= 3) {
        output_dir = argv[2];
    }

    auto params = msr::GenerateParameters();
    const auto output = msr::RunSimulation(params, steps, output_dir);
    const std::size_t last = output.time.empty() ? 0 : output.time.size() - 1;
    std::cout
        << "steps=" << steps
        << " final_time_s=" << output.time[last]
        << " phi_mid=" << output.phi_mid[last]
        << " rho=" << output.rho[last]
        << " power=" << output.power[last]
        << " fuel_mid=" << output.fuel_mid[last]
        << " graphite_mid=" << output.graphite_mid[last]
        << '\n';
    return 0;
}
