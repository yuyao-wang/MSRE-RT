import argparse
from pathlib import Path

import numpy as np

try:
    from . import path_setup
except ImportError:  # pragma: no cover - direct script execution
    import path_setup
from parameters import generate_parameters
from verification_physics import equivalent_fission_source, steady_precursor_profiles
from verification_utils import iso_timestamp, write_csv, write_json


OUTPUT_DIR = path_setup.REPO_ROOT / "Verification_Evaluation" / "outputs" / "external_validation"

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


def build_parser():
    parser = argparse.ArgumentParser(description="Run delayed-neutron circulation-loss external validation.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Directory for CSV/JSON outputs.")
    parser.add_argument("--nodes", type=int, nargs="+", default=[80, 120, 160, 240], help="MSRE-input axial grids.")
    parser.add_argument("--reported-n", type=int, default=160, help="Grid size highlighted in the console/summary.")
    parser.add_argument("--steady-steps", type=int, default=None, help="Override steady-state spinup steps for all MSRE grids.")
    parser.add_argument("--benchmark-loss-pcm", type=float, default=BENCHMARK_LOSS_PCM)
    parser.add_argument("--benchmark-sigma-pcm", type=float, default=BENCHMARK_SIGMA_PCM)
    parser.add_argument("--serpent-loss-pcm", type=float, default=SERPENT_LOSS_PCM)
    parser.add_argument("--serpent-sigma-pcm", type=float, default=SERPENT_SIGMA_PCM)
    parser.add_argument("--msre-velocity-cm-s", type=float, default=MSRE_CHANNEL_VELOCITY_CM_S)
    parser.add_argument("--msre-loop-time-s", type=float, default=MSRE_TOTAL_LOOP_TIME_S)
    parser.add_argument("--msre-out-of-core-fraction", type=float, default=MSRE_OUT_OF_CORE_FRACTION)
    parser.add_argument("--msre-loop-tau-s", type=float, default=None, help="Override MSRE out-of-core residence time.")
    parser.add_argument("--skip-present-verification", action="store_true", help="Skip the artificial present-beta comparison row.")
    parser.add_argument("--present-nodes", type=int, default=160)
    parser.add_argument("--present-velocity-cm-s", type=float, default=20.0)
    parser.add_argument("--present-loop-tau-s", type=float, default=16.73)
    parser.add_argument("--present-steady-steps", type=int, default=60)
    return parser


def main():
    args = build_parser().parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    msre_loop_tau_s = (
        args.msre_loop_tau_s
        if args.msre_loop_tau_s is not None
        else args.msre_loop_time_s * args.msre_out_of_core_fraction
    )
    validation_rows = []
    for n_nodes in args.nodes:
        beta_s, beta_c, loss = circulation_loss_pcm(
            beta=MSRE_EFFECTIVE_BETA,
            lambda_i=MSRE_LAMBDA,
            n_nodes=n_nodes,
            velocity_cm_s=args.msre_velocity_cm_s,
            loop_tau_s=msre_loop_tau_s,
            steady_steps=args.steady_steps if args.steady_steps is not None else (40 if n_nodes <= 160 else 20),
        )
        validation_rows.append(
            {
                "case": f"MSRE_effective_beta_N{n_nodes}",
                "N_z": n_nodes,
                "beta_stationary": beta_s,
                "beta_circulating": beta_c,
                "circulation_loss_pcm": loss,
                "benchmark_loss_pcm": args.benchmark_loss_pcm,
                "benchmark_sigma_pcm": args.benchmark_sigma_pcm,
                "serpent_loss_pcm": args.serpent_loss_pcm,
                "serpent_sigma_pcm": args.serpent_sigma_pcm,
                "error_vs_benchmark_pcm": loss - args.benchmark_loss_pcm,
                "abs_error_vs_benchmark_pcm": abs(loss - args.benchmark_loss_pcm),
                "relative_error_vs_benchmark_percent": 100.0
                * abs(loss - args.benchmark_loss_pcm)
                / args.benchmark_loss_pcm,
                "C_over_E": loss / args.benchmark_loss_pcm,
                "velocity_cm_s": args.msre_velocity_cm_s,
                "loop_tau_s": msre_loop_tau_s,
                "input_scope": "MSRE effective delayed fractions and benchmark out-of-core residence time",
            }
        )

    present_row = None
    if not args.skip_present_verification:
        beta_s, beta_c, loss = circulation_loss_pcm(
            beta=CURRENT_VERIFICATION_BETA,
            lambda_i=CURRENT_VERIFICATION_LAMBDA,
            n_nodes=args.present_nodes,
            velocity_cm_s=args.present_velocity_cm_s,
            loop_tau_s=args.present_loop_tau_s,
            steady_steps=args.present_steady_steps,
        )
        present_row = {
            "case": f"present_verification_beta_N{args.present_nodes}",
            "N_z": args.present_nodes,
            "beta_stationary": beta_s,
            "beta_circulating": beta_c,
            "circulation_loss_pcm": loss,
            "benchmark_loss_pcm": args.benchmark_loss_pcm,
            "benchmark_sigma_pcm": args.benchmark_sigma_pcm,
            "serpent_loss_pcm": args.serpent_loss_pcm,
            "serpent_sigma_pcm": args.serpent_sigma_pcm,
            "error_vs_benchmark_pcm": loss - args.benchmark_loss_pcm,
            "abs_error_vs_benchmark_pcm": abs(loss - args.benchmark_loss_pcm),
            "relative_error_vs_benchmark_percent": 100.0 * abs(loss - args.benchmark_loss_pcm) / args.benchmark_loss_pcm,
            "C_over_E": loss / args.benchmark_loss_pcm,
            "velocity_cm_s": args.present_velocity_cm_s,
            "loop_tau_s": args.present_loop_tau_s,
            "input_scope": "present artificial verification delayed-neutron set; not used as MSRE benchmark input",
        }
        validation_rows.append(present_row)

    fieldnames = list(validation_rows[0].keys())
    write_csv(output_dir / "table_V2_external_circulation_validation.csv", fieldnames, validation_rows)

    reported = next(
        (row for row in validation_rows if row["case"] == f"MSRE_effective_beta_N{args.reported_n}"),
        validation_rows[0],
    )
    write_json(
        output_dir / "external_circulation_validation_summary.json",
        {
            "generated_at": iso_timestamp(),
            "external_reference": {
                "benchmark_loss_pcm": args.benchmark_loss_pcm,
                "benchmark_sigma_pcm": args.benchmark_sigma_pcm,
                "serpent_loss_pcm": args.serpent_loss_pcm,
                "serpent_sigma_pcm": args.serpent_sigma_pcm,
            },
            "reported_case": reported,
            "grid_rows": [row for row in validation_rows if row["case"].startswith("MSRE_effective_beta")],
            "present_verification_beta_row": present_row,
        },
    )

    print("External circulation benchmark summary")
    print(f"N={reported['N_z']} MSRE-input loss: {reported['circulation_loss_pcm']:.3f} pcm")
    print(f"Benchmark loss: {args.benchmark_loss_pcm:.1f} +/- {args.benchmark_sigma_pcm:.1f} pcm")
    print(f"Absolute error: {reported['abs_error_vs_benchmark_pcm']:.3f} pcm")
    print(f"C/E: {reported['C_over_E']:.3f}")
    print(f"CSV: {output_dir / 'table_V2_external_circulation_validation.csv'}")


if __name__ == "__main__":
    main()
