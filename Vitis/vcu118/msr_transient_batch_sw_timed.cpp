#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

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
        auto states = base_states;
        auto delays = base_delays;
        auto params = base_params;
        std::vector<msr_vitis::StepDiagnostics> final_diags(scenario_count_u);

        const auto start = std::chrono::steady_clock::now();
        msr_vitis::msr_transient_batch_kernel(
            states.data(),
            delays.data(),
            params.data(),
            rod_positions.data(),
            external_reactivities.data(),
            final_diags.data(),
            step_count,
            scenario_count
        );
        const auto end = std::chrono::steady_clock::now();
        const double total_us = std::chrono::duration<double, std::micro>(end - start).count();

        for (std::size_t scenario = 0; scenario < scenario_count_u; ++scenario) {
            checksum += final_diags[scenario].power + final_diags[scenario].brayton_return;
        }

        if (iter >= warmup) {
            update_stats(total_stats, total_us);
            last_states = std::move(states);
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
