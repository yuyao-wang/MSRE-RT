from pathlib import Path

import numpy as np

from parameters import generate_parameters
from paper_physics import equivalent_fission_source, steady_precursor_profiles
from paper_utils import iso_timestamp, write_csv, write_json


OUTPUT_DIR = Path("paper_writing") / "Pictures"

BENCHMARK_LOSS_PCM = 212.0
BENCHMARK_SIGMA_PCM = 6.0
SERPENT_LOSS_PCM = 222.0
SERPENT_SIGMA_PCM = 10.0

MSRE_EFFECTIVE_BETA = tuple(np.asarray([2.23, 14.57, 13.07, 26.28, 7.66, 2.80]) * 1.0e-4)
MSRE_LAMBDA = (0.0124, 0.0305, 0.1114, 0.3013, 1.140, 3.010)
MSRE_CHANNEL_VELOCITY_CM_S = 17.71
MSRE_TOTAL_LOOP_TIME_S = 25.2
MSRE_OUT_OF_CORE_FRACTION = 0.32
MSRE_OUT_OF_CORE_TIME_S = MSRE_TOTAL_LOOP_TIME_S * MSRE_OUT_OF_CORE_FRACTION

CURRENT_VERIFICATION_BETA = (0.000228, 0.000788, 0.000664, 0.000736, 0.000136, 0.000088)
CURRENT_VERIFICATION_LAMBDA = (0.0126, 0.0337, 0.139, 0.325, 1.13, 2.5)


def circulation_loss_pcm(
    *,
    beta,
    lambda_i,
    n_nodes,
    velocity_cm_s,
    loop_tau_s,
    steady_steps,
):
    params = generate_parameters(
        N=n_nodes,
        steady_state_steps=steady_steps,
        precursor_loop_efficiency=1.0,
        beta=beta,
        lambda_i=lambda_i,
        v_core=velocity_cm_s,
        tau_l=loop_tau_s,
        use_steady_state_initialization=True,
    )
    critical_scale = float(params.get("critical_fission_scale", 1.0))
    fission_source = critical_scale * equivalent_fission_source(params)
    z = np.asarray(params["z"], dtype=float)
    lambdas = np.asarray(params["lambda_i_np"], dtype=float)

    stationary = steady_precursor_profiles(
        params,
        fission_source=fission_source,
        mode="stationary",
    )
    recirculating = steady_precursor_profiles(
        params,
        fission_source=fission_source,
        mode="recirculation",
        loop_efficiency=1.0,
        loop_tau=loop_tau_s,
    )

    fission_integral = float(np.trapezoid(fission_source, z))
    beta_stationary = float(
        np.trapezoid(np.sum(lambdas[:, None] * stationary, axis=0), z)
        / max(fission_integral, 1.0e-30)
    )
    beta_circulating = float(
        np.trapezoid(np.sum(lambdas[:, None] * recirculating, axis=0), z)
        / max(fission_integral, 1.0e-30)
    )
    loss_pcm = 1.0e5 * (beta_stationary - beta_circulating)
    return beta_stationary, beta_circulating, loss_pcm


def main():
    validation_rows = []
    for n_nodes in (80, 120, 160, 240):
        beta_s, beta_c, loss = circulation_loss_pcm(
            beta=MSRE_EFFECTIVE_BETA,
            lambda_i=MSRE_LAMBDA,
            n_nodes=n_nodes,
            velocity_cm_s=MSRE_CHANNEL_VELOCITY_CM_S,
            loop_tau_s=MSRE_OUT_OF_CORE_TIME_S,
            steady_steps=40 if n_nodes <= 160 else 20,
        )
        validation_rows.append(
            {
                "case": f"MSRE_effective_beta_N{n_nodes}",
                "N_z": n_nodes,
                "beta_stationary": beta_s,
                "beta_circulating": beta_c,
                "circulation_loss_pcm": loss,
                "benchmark_loss_pcm": BENCHMARK_LOSS_PCM,
                "benchmark_sigma_pcm": BENCHMARK_SIGMA_PCM,
                "serpent_loss_pcm": SERPENT_LOSS_PCM,
                "serpent_sigma_pcm": SERPENT_SIGMA_PCM,
                "error_vs_benchmark_pcm": loss - BENCHMARK_LOSS_PCM,
                "abs_error_vs_benchmark_pcm": abs(loss - BENCHMARK_LOSS_PCM),
                "relative_error_vs_benchmark_percent": 100.0
                * abs(loss - BENCHMARK_LOSS_PCM)
                / BENCHMARK_LOSS_PCM,
                "C_over_E": loss / BENCHMARK_LOSS_PCM,
                "velocity_cm_s": MSRE_CHANNEL_VELOCITY_CM_S,
                "loop_tau_s": MSRE_OUT_OF_CORE_TIME_S,
                "input_scope": "MSRE effective delayed fractions and benchmark out-of-core residence time",
            }
        )

    beta_s, beta_c, loss = circulation_loss_pcm(
        beta=CURRENT_VERIFICATION_BETA,
        lambda_i=CURRENT_VERIFICATION_LAMBDA,
        n_nodes=160,
        velocity_cm_s=20.0,
        loop_tau_s=16.73,
        steady_steps=60,
    )
    validation_rows.append(
        {
            "case": "present_verification_beta_N160",
            "N_z": 160,
            "beta_stationary": beta_s,
            "beta_circulating": beta_c,
            "circulation_loss_pcm": loss,
            "benchmark_loss_pcm": BENCHMARK_LOSS_PCM,
            "benchmark_sigma_pcm": BENCHMARK_SIGMA_PCM,
            "serpent_loss_pcm": SERPENT_LOSS_PCM,
            "serpent_sigma_pcm": SERPENT_SIGMA_PCM,
            "error_vs_benchmark_pcm": loss - BENCHMARK_LOSS_PCM,
            "abs_error_vs_benchmark_pcm": abs(loss - BENCHMARK_LOSS_PCM),
            "relative_error_vs_benchmark_percent": 100.0 * abs(loss - BENCHMARK_LOSS_PCM) / BENCHMARK_LOSS_PCM,
            "C_over_E": loss / BENCHMARK_LOSS_PCM,
            "velocity_cm_s": 20.0,
            "loop_tau_s": 16.73,
            "input_scope": "present artificial verification delayed-neutron set; not used as MSRE benchmark input",
        }
    )

    fieldnames = list(validation_rows[0].keys())
    write_csv(OUTPUT_DIR / "table_V2_external_circulation_validation.csv", fieldnames, validation_rows)

    n160 = next(row for row in validation_rows if row["case"] == "MSRE_effective_beta_N160")
    write_json(
        OUTPUT_DIR / "external_circulation_validation_summary.json",
        {
            "generated_at": iso_timestamp(),
            "external_reference": {
                "benchmark_loss_pcm": BENCHMARK_LOSS_PCM,
                "benchmark_sigma_pcm": BENCHMARK_SIGMA_PCM,
                "serpent_loss_pcm": SERPENT_LOSS_PCM,
                "serpent_sigma_pcm": SERPENT_SIGMA_PCM,
            },
            "reported_case": n160,
            "grid_rows": validation_rows[:4],
            "present_verification_beta_row": validation_rows[-1],
        },
    )

    print("External circulation benchmark summary")
    print(f"N=160 MSRE-input loss: {n160['circulation_loss_pcm']:.3f} pcm")
    print(f"Benchmark loss: {BENCHMARK_LOSS_PCM:.1f} +/- {BENCHMARK_SIGMA_PCM:.1f} pcm")
    print(f"Absolute error: {n160['abs_error_vs_benchmark_pcm']:.3f} pcm")
    print(f"C/E: {n160['C_over_E']:.3f}")
    print(f"CSV: {OUTPUT_DIR / 'table_V2_external_circulation_validation.csv'}")


if __name__ == "__main__":
    main()
