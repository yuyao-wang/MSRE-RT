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

#include "../msr_vitis_module_tops.cpp"

namespace {

template <typename T>
T read_blob(const std::string& path) {
    static_assert(std::is_trivially_copyable<T>::value, "blob type must be trivially copyable");
    T value{};
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("failed to open " + path);
    }
    input.read(reinterpret_cast<char*>(&value), static_cast<std::streamsize>(sizeof(T)));
    if (input.gcount() != static_cast<std::streamsize>(sizeof(T))) {
        throw std::runtime_error("short read for " + path);
    }
    return value;
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
    if (argc != 13 && argc != 14) {
        std::cerr << "usage: " << argv[0]
                  << " <core_state.bin> <core_params.bin> <bop_state.bin> <bop_params.bin>"
                  << " <Ts_core_inlet> <rod_position> <external_reactivity>"
                  << " <Ts_HX1_L> <Tss_HX1_0> <Tss_HX2_L> <Tsss_HX2_0>"
                  << " <repeats> [warmup]\n";
        return 2;
    }

    const std::string core_state_path = argv[1];
    const std::string core_params_path = argv[2];
    const std::string bop_state_path = argv[3];
    const std::string bop_params_path = argv[4];
    const double Ts_core_inlet = std::strtod(argv[5], nullptr);
    const double rod_position = std::strtod(argv[6], nullptr);
    const double external_reactivity = std::strtod(argv[7], nullptr);
    const double Ts_HX1_L = std::strtod(argv[8], nullptr);
    const double Tss_HX1_0 = std::strtod(argv[9], nullptr);
    const double Tss_HX2_L = std::strtod(argv[10], nullptr);
    const double Tsss_HX2_0 = std::strtod(argv[11], nullptr);
    const int repeats = std::atoi(argv[12]);
    const int warmup = (argc == 13) ? 0 : std::atoi(argv[13]);

    if (repeats <= 0) {
        throw std::runtime_error("repeats must be > 0");
    }
    if (warmup < 0) {
        throw std::runtime_error("warmup must be >= 0");
    }

    const CoreStepState base_core_state = read_blob<CoreStepState>(core_state_path);
    const KernelParams core_params = read_blob<KernelParams>(core_params_path);
    const BopStepState base_bop_state = read_blob<BopStepState>(bop_state_path);
    const KernelParams bop_params = read_blob<KernelParams>(bop_params_path);

    TimingStats core_stats{};
    TimingStats bop_stats{};
    CoreStepBoundary last_core_boundary{};
    BopStepBoundary last_bop_boundary{};
    volatile double checksum = 0.0;

    for (int iter = 0; iter < warmup + repeats; ++iter) {
        CoreStepState core_state = base_core_state;
        CoreStepBoundary core_boundary{};
        const auto core_start = std::chrono::steady_clock::now();
        core_step_kernel_n200_s1(&core_state, &core_params, Ts_core_inlet, rod_position, external_reactivity, &core_boundary);
        const auto core_end = std::chrono::steady_clock::now();
        const double core_us = std::chrono::duration<double, std::micro>(core_end - core_start).count();

        BopStepState bop_state = base_bop_state;
        BopStepBoundary bop_boundary{};
        const auto bop_start = std::chrono::steady_clock::now();
        bop_step_kernel_n200_s1(&bop_state, &bop_params, Ts_HX1_L, Tss_HX1_0, Tss_HX2_L, Tsss_HX2_0, &bop_boundary);
        const auto bop_end = std::chrono::steady_clock::now();
        const double bop_us = std::chrono::duration<double, std::micro>(bop_end - bop_start).count();

        checksum += core_boundary.power + bop_boundary.Tsss_pp_0;

        if (iter >= warmup) {
            update_stats(core_stats, core_us);
            update_stats(bop_stats, bop_us);
            last_core_boundary = core_boundary;
            last_bop_boundary = bop_boundary;
        }
    }

    std::cout << std::setprecision(17);
    std::cout << "timing.repeats=" << repeats << "\n";
    std::cout << "timing.warmup=" << warmup << "\n";
    std::cout << "timing.core.min_us=" << core_stats.min_us << "\n";
    std::cout << "timing.core.max_us=" << core_stats.max_us << "\n";
    std::cout << "timing.core.avg_us=" << avg_us(core_stats, repeats) << "\n";
    std::cout << "timing.bop.min_us=" << bop_stats.min_us << "\n";
    std::cout << "timing.bop.max_us=" << bop_stats.max_us << "\n";
    std::cout << "timing.bop.avg_us=" << avg_us(bop_stats, repeats) << "\n";
    std::cout << "core.rho=" << last_core_boundary.rho << "\n";
    std::cout << "core.power=" << last_core_boundary.power << "\n";
    std::cout << "core.phi_mid=" << last_core_boundary.phi_mid << "\n";
    std::cout << "core.fuel_mid=" << last_core_boundary.fuel_mid << "\n";
    std::cout << "core.graphite_mid=" << last_core_boundary.graphite_mid << "\n";
    std::cout << "core.Ts_core_inlet=" << last_core_boundary.Ts_core_inlet << "\n";
    std::cout << "core.Ts_core_outlet=" << last_core_boundary.Ts_core_outlet << "\n";
    std::cout << "bop.Ts_HX1_0=" << last_bop_boundary.Ts_HX1_0 << "\n";
    std::cout << "bop.Tss_HX1_L=" << last_bop_boundary.Tss_HX1_L << "\n";
    std::cout << "bop.Tss_HX2_0=" << last_bop_boundary.Tss_HX2_0 << "\n";
    std::cout << "bop.Tsss_HX2_L=" << last_bop_boundary.Tsss_HX2_L << "\n";
    std::cout << "bop.Tsss_pp_0=" << last_bop_boundary.Tsss_pp_0 << "\n";
    std::cout << "timing.checksum=" << checksum << "\n";
    return 0;
}
