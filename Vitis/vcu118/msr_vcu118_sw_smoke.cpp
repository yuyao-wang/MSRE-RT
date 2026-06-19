#include <cstddef>
#include <cstdint>
#include <fstream>
#include <cstdlib>
#include <iomanip>
#include <iostream>
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

template <typename T>
void print_size(const char* name) {
    std::cout << name << "=" << sizeof(T) << "\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 5 && argc != 10) {
        std::cerr << "usage: " << argv[0]
                  << " <core_state.bin> <core_params.bin> <bop_state.bin> <bop_params.bin>"
                  << " [Ts_core_inlet Ts_HX1_L Tss_HX1_0 Tss_HX2_L Tsss_HX2_0]\n";
        return 2;
    }

    const std::string core_state_path = argv[1];
    const std::string core_params_path = argv[2];
    const std::string bop_state_path = argv[3];
    const std::string bop_params_path = argv[4];
    const double Ts_core_inlet = (argc == 10) ? std::strtod(argv[5], nullptr) : 900.0;
    const double Ts_HX1_L = (argc == 10) ? std::strtod(argv[6], nullptr) : 930.0;
    const double Tss_HX1_0 = (argc == 10) ? std::strtod(argv[7], nullptr) : 650.0;
    const double Tss_HX2_L = (argc == 10) ? std::strtod(argv[8], nullptr) : 640.0;
    const double Tsss_HX2_0 = (argc == 10) ? std::strtod(argv[9], nullptr) : 500.0;

    print_size<CoreStepState>("sizeof(CoreStepState)");
    print_size<BopStepState>("sizeof(BopStepState)");
    print_size<KernelParams>("sizeof(KernelParams)");
    print_size<CoreStepBoundary>("sizeof(CoreStepBoundary)");
    print_size<BopStepBoundary>("sizeof(BopStepBoundary)");

    CoreStepState core_state = read_blob<CoreStepState>(core_state_path);
    KernelParams core_params = read_blob<KernelParams>(core_params_path);
    BopStepState bop_state = read_blob<BopStepState>(bop_state_path);
    KernelParams bop_params = read_blob<KernelParams>(bop_params_path);

    CoreStepBoundary core_boundary{};
    BopStepBoundary bop_boundary{};

    core_step_kernel_n200_s1(&core_state, &core_params, Ts_core_inlet, 0.0, 0.0, &core_boundary);
    bop_step_kernel_n200_s1(&bop_state, &bop_params, Ts_HX1_L, Tss_HX1_0, Tss_HX2_L, Tsss_HX2_0, &bop_boundary);

    std::cout << std::setprecision(17);
    std::cout << "core.rho=" << core_boundary.rho << "\n";
    std::cout << "core.power=" << core_boundary.power << "\n";
    std::cout << "core.phi_mid=" << core_boundary.phi_mid << "\n";
    std::cout << "core.fuel_mid=" << core_boundary.fuel_mid << "\n";
    std::cout << "core.graphite_mid=" << core_boundary.graphite_mid << "\n";
    std::cout << "core.Ts_core_inlet=" << core_boundary.Ts_core_inlet << "\n";
    std::cout << "core.Ts_core_outlet=" << core_boundary.Ts_core_outlet << "\n";

    std::cout << "bop.Ts_HX1_0=" << bop_boundary.Ts_HX1_0 << "\n";
    std::cout << "bop.Tss_HX1_L=" << bop_boundary.Tss_HX1_L << "\n";
    std::cout << "bop.Tss_HX2_0=" << bop_boundary.Tss_HX2_0 << "\n";
    std::cout << "bop.Tsss_HX2_L=" << bop_boundary.Tsss_HX2_L << "\n";
    std::cout << "bop.Tsss_pp_0=" << bop_boundary.Tsss_pp_0 << "\n";

    return 0;
}
