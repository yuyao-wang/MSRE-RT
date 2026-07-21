#pragma once

#include <algorithm>
#include <cmath>

namespace msr_shared {

constexpr int kPointKineticsPrecursorGroups = 6;
constexpr int kPointKineticsStateSize = 1 + kPointKineticsPrecursorGroups;

#ifndef MSR_POINT_KINETICS_SOLVER
#define MSR_POINT_KINETICS_SOLVER 0
#endif

inline double pk_safe_divisor(double value) {
    if (std::abs(value) >= 1.0e-12) {
        return value;
    }
    return (value < 0.0) ? -1.0e-12 : 1.0e-12;
}

inline void pk_zero_matrix(double matrix[kPointKineticsStateSize][kPointKineticsStateSize]) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            matrix[row][col] = 0.0;
        }
    }
}

inline void pk_identity_matrix(double matrix[kPointKineticsStateSize][kPointKineticsStateSize]) {
    pk_zero_matrix(matrix);
    for (int idx = 0; idx < kPointKineticsStateSize; ++idx) {
        matrix[idx][idx] = 1.0;
    }
}

inline void pk_copy_matrix(
    const double src[kPointKineticsStateSize][kPointKineticsStateSize],
    double dst[kPointKineticsStateSize][kPointKineticsStateSize]
) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            dst[row][col] = src[row][col];
        }
    }
}

inline void pk_scale_matrix(
    double matrix[kPointKineticsStateSize][kPointKineticsStateSize],
    double factor
) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            matrix[row][col] *= factor;
        }
    }
}

inline double pk_matrix_norm1(
    const double matrix[kPointKineticsStateSize][kPointKineticsStateSize]
) {
    double norm = 0.0;
    for (int col = 0; col < kPointKineticsStateSize; ++col) {
        double column_sum = 0.0;
        for (int row = 0; row < kPointKineticsStateSize; ++row) {
            column_sum += std::abs(matrix[row][col]);
        }
        norm = std::max(norm, column_sum);
    }
    return norm;
}

inline void pk_add_inplace(
    double lhs[kPointKineticsStateSize][kPointKineticsStateSize],
    const double rhs[kPointKineticsStateSize][kPointKineticsStateSize]
) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            lhs[row][col] += rhs[row][col];
        }
    }
}

inline void pk_multiply_matrix(
    const double lhs[kPointKineticsStateSize][kPointKineticsStateSize],
    const double rhs[kPointKineticsStateSize][kPointKineticsStateSize],
    double out[kPointKineticsStateSize][kPointKineticsStateSize]
) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            double sum = 0.0;
            for (int k = 0; k < kPointKineticsStateSize; ++k) {
                sum += lhs[row][k] * rhs[k][col];
            }
            out[row][col] = sum;
        }
    }
}

inline void pk_multiply_vector(
    const double matrix[kPointKineticsStateSize][kPointKineticsStateSize],
    const double vector[kPointKineticsStateSize],
    double out[kPointKineticsStateSize]
) {
    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        double sum = 0.0;
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            sum += matrix[row][col] * vector[col];
        }
        out[row] = sum;
    }
}

inline void pk_matrix_exponential(
    const double operator_matrix[kPointKineticsStateSize][kPointKineticsStateSize],
    double out[kPointKineticsStateSize][kPointKineticsStateSize]
) {
    double scaled[kPointKineticsStateSize][kPointKineticsStateSize];
    pk_copy_matrix(operator_matrix, scaled);

    double norm = pk_matrix_norm1(scaled);
    int squarings = 0;
    while (norm > 0.5) {
        norm *= 0.5;
        ++squarings;
    }
    pk_scale_matrix(scaled, std::ldexp(1.0, -squarings));

    pk_identity_matrix(out);

    double term[kPointKineticsStateSize][kPointKineticsStateSize];
    pk_identity_matrix(term);

    for (int order = 1; order <= 20; ++order) {
        double product[kPointKineticsStateSize][kPointKineticsStateSize];
        pk_multiply_matrix(term, scaled, product);
        pk_copy_matrix(product, term);
        pk_scale_matrix(term, 1.0 / static_cast<double>(order));
        pk_add_inplace(out, term);
    }

    for (int idx = 0; idx < squarings; ++idx) {
        double squared[kPointKineticsStateSize][kPointKineticsStateSize];
        pk_multiply_matrix(out, out, squared);
        pk_copy_matrix(squared, out);
    }
}

inline void initialize_point_kinetics_state(
    const double beta[kPointKineticsPrecursorGroups],
    const double lambda_i[kPointKineticsPrecursorGroups],
    double beta_total_reference,
    double effective_beta_total,
    double prompt_generation_time,
    double* amplitude,
    double precursor_state[kPointKineticsPrecursorGroups],
    double beta_effective[kPointKineticsPrecursorGroups]
) {
    const double beta_scale = effective_beta_total / std::max(beta_total_reference, 1.0e-12);
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        beta_effective[group] = beta[group] * beta_scale;
        precursor_state[group] =
            beta_effective[group] /
            std::max(prompt_generation_time, 1.0e-12) /
            std::max(lambda_i[group], 1.0e-12);
    }
    *amplitude = 1.0;
}

inline void advance_point_kinetics(
    const double beta_effective[kPointKineticsPrecursorGroups],
    const double lambda_i[kPointKineticsPrecursorGroups],
    double prompt_generation_time,
    double rho,
    double dt,
    double* amplitude,
    double precursor_state[kPointKineticsPrecursorGroups]
) {
    double beta_total = 0.0;
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        beta_total += beta_effective[group];
    }

    const double safe_prompt_generation_time = std::max(prompt_generation_time, 1.0e-12);
    const double amplitude_old = *amplitude;
    const double a = (rho - beta_total) / safe_prompt_generation_time;

#if MSR_POINT_KINETICS_SOLVER == 1
    double numerator = amplitude_old;
    double denominator = 1.0 - dt * a;

    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        const double lambda = lambda_i[group];
        const double b = beta_effective[group] / safe_prompt_generation_time;
        const double c_denominator = 1.0 + dt * lambda;
        numerator += dt * lambda * precursor_state[group] / c_denominator;
        denominator -= dt * dt * lambda * b / c_denominator;
    }

    const double amplitude_new = numerator / pk_safe_divisor(denominator);
    *amplitude = std::max(amplitude_new, 0.0);

    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        const double lambda = lambda_i[group];
        const double b = beta_effective[group] / safe_prompt_generation_time;
        const double c_denominator = 1.0 + dt * lambda;
        const double updated = (precursor_state[group] + dt * b * amplitude_new) / c_denominator;
        precursor_state[group] = std::max(updated, 0.0);
    }
    return;
#elif MSR_POINT_KINETICS_SOLVER == 2
    const double alpha = 0.5 * dt;
    double delayed_source_old = 0.0;
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        delayed_source_old += lambda_i[group] * precursor_state[group];
    }

    const double rhs = amplitude_old + alpha * (a * amplitude_old + delayed_source_old);
    double source_numerator = 0.0;
    double source_denominator = 0.0;
    double precursor_numerators[kPointKineticsPrecursorGroups];

    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        const double lambda = lambda_i[group];
        const double b = beta_effective[group] / safe_prompt_generation_time;
        const double c_denominator = 1.0 + alpha * lambda;
        const double c_numerator = (1.0 - alpha * lambda) * precursor_state[group] + alpha * b * amplitude_old;
        precursor_numerators[group] = c_numerator;
        source_numerator += lambda * c_numerator / c_denominator;
        source_denominator += lambda * b / c_denominator;
    }

    const double amplitude_denominator =
        1.0 - alpha * a - alpha * alpha * source_denominator;
    const double amplitude_new =
        (rhs + alpha * source_numerator) / pk_safe_divisor(amplitude_denominator);
    *amplitude = std::max(amplitude_new, 0.0);

    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        const double lambda = lambda_i[group];
        const double b = beta_effective[group] / safe_prompt_generation_time;
        const double c_denominator = 1.0 + alpha * lambda;
        const double updated =
            (precursor_numerators[group] + alpha * b * amplitude_new) / c_denominator;
        precursor_state[group] = std::max(updated, 0.0);
    }
    return;
#else
    double operator_matrix[kPointKineticsStateSize][kPointKineticsStateSize];
    pk_zero_matrix(operator_matrix);

    operator_matrix[0][0] = a;
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        operator_matrix[0][1 + group] = lambda_i[group];
        operator_matrix[1 + group][0] = beta_effective[group] / safe_prompt_generation_time;
        operator_matrix[1 + group][1 + group] = -lambda_i[group];
    }

    for (int row = 0; row < kPointKineticsStateSize; ++row) {
        for (int col = 0; col < kPointKineticsStateSize; ++col) {
            operator_matrix[row][col] *= dt;
        }
    }

    double propagator[kPointKineticsStateSize][kPointKineticsStateSize];
    pk_matrix_exponential(operator_matrix, propagator);

    double state[kPointKineticsStateSize];
    state[0] = amplitude_old;
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        state[1 + group] = precursor_state[group];
    }

    double updated[kPointKineticsStateSize];
    pk_multiply_vector(propagator, state, updated);

    *amplitude = std::max(updated[0], 0.0);
    for (int group = 0; group < kPointKineticsPrecursorGroups; ++group) {
        precursor_state[group] = std::max(updated[1 + group], 0.0);
    }
#endif
}

}  // namespace msr_shared
