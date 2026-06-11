from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass

import numpy as np

from HX1 import HX1
from HX2 import HX2
from cross_sections import build_cross_sections
from neutronics import _extract_state, neutronics
from paper_physics import (
    build_event_state,
    compute_reactivity_from_xs,
    make_reference_k,
    run_coupled_transient,
    trapz,
)
from parameters import generate_parameters
from power_plant import power_plant_temp
from thermal_hydraulics import thermal_hydraulics


def _initial_column(params, key, size):
    value = params.get(key)
    if value is None:
        return np.zeros((size, 1), dtype=float)
    array = np.asarray(value, dtype=float).reshape(size, 1)
    return array.copy()


@dataclass
class DelayChannel:
    delay_steps: int
    history_step_offset: int = 0
    initial_buffer: list[float] | None = None

    def __post_init__(self):
        self.samples: dict[int, float] = {}
        if not self.initial_buffer:
            return
        start_step = self.history_step_offset - self.delay_steps
        for idx, value in enumerate(self.initial_buffer):
            self.samples[start_step + idx] = float(value)

    def read(self, step: int, fallback: float) -> float:
        if step < self.delay_steps:
            return float(fallback)
        source_step = step - self.delay_steps
        if source_step not in self.samples:
            raise KeyError(
                f"Missing delayed sample for step {source_step}; "
                f"consumer step={step}, delay_steps={self.delay_steps}"
            )
        return self.samples[source_step]

    def submit(self, step: int, value: float) -> None:
        if step in self.samples:
            raise ValueError(f"Duplicate delayed sample for step {step}")
        self.samples[step] = float(value)


def _make_delay_channels(params):
    outer_dt = float(params.get("outer_dt", 1.0))
    history_step_offset = int(params.get("history_step_offset", 0))

    def channel(delay_key, buffer_key):
        delay_steps = max(int(round(float(params[delay_key]) / max(outer_dt, 1.0e-12))), 0)
        return DelayChannel(
            delay_steps=delay_steps,
            history_step_offset=history_step_offset,
            initial_buffer=list(np.asarray(params.get(buffer_key, []), dtype=float)),
        )

    return {
        "hx_c": channel("tau_hx_c", "buffer_hx_c_init"),
        "c_hx": channel("tau_c_hx", "buffer_c_hx_init"),
        "r_hx": channel("tau_r_hx", "buffer_r_hx_init"),
        "hx_r": channel("tau_hx_r", "buffer_hx_r_init"),
        "r_pp": channel("tau_r_pp", "buffer_r_pp_init"),
        "pp_r": channel("tau_pp_r", "buffer_pp_r_init"),
    }


def run_async_split_transient(
    params,
    num_steps,
    event_sequence=None,
    record_fields=None,
    diagnostic_mode="eigenvalue",
    execution_order="bop_then_core",
):
    if execution_order not in {"core_then_bop", "bop_then_core"}:
        raise ValueError("execution_order must be 'core_then_bop' or 'bop_then_core'")

    params = copy.deepcopy(params)
    record_fields = set(record_fields or [])
    outer_dt = float(params.get("outer_dt", 1.0))
    z = np.asarray(params["z"], dtype=float)
    n = int(params["N"])
    nx = int(params["Nx"])
    history_step_offset = int(params.get("history_step_offset", 0))

    reference_k_raw, phi_guess = make_reference_k(params)

    y_n = _initial_column(params, "y_n_init", params["neutronics_state_size"])
    y_th = _initial_column(params, "y_th_init", 2 * n)
    y_hx1 = _initial_column(params, "y_hx1_init", 2 * nx)
    y_hx2 = _initial_column(params, "y_hx2_init", 2 * nx)
    if "y_hx1_init" not in params:
        y_hx1[:, 0] = np.concatenate([params["u_init"], params["v_init"]])
    if "y_hx2_init" not in params:
        y_hx2[:, 0] = np.concatenate([params["u2_init"], params["v2_init"]])

    if "y_th_init" in params:
        temperature_fuel = np.asarray(y_th[:n, 0], dtype=float).copy()
        temperature_graphite = np.asarray(y_th[n:, 0], dtype=float).copy()
    else:
        temperature_fuel = np.asarray(params["initialS"], dtype=float).copy()
        temperature_graphite = np.asarray(params["initialG"], dtype=float).copy()

    channels = _make_delay_channels(params)

    base_ts_in = float(params["Ts_in"])
    base_ts_out = float(params["Ts_out"])
    base_tss_in = float(params["Tss_in"])
    base_tss_out = float(params["Tss_out"])
    base_tsss_in = float(params["Tsss_in"])
    base_tsss_out = float(params["Tsss_out"])
    carry_bop_feedback = {
        "ts_hx1_0": float(params["Ts_in"]),
        "tss_hx2_0": float(params["Tss_in"]),
        "tsss_pp_0": float(params["Tsss_in"]),
    }

    time_s = outer_dt * np.arange(int(num_steps), dtype=float)
    power_history = np.zeros(num_steps, dtype=float)
    rho_history_pcm = np.zeros(num_steps, dtype=float)
    ts_in_history = np.zeros(num_steps, dtype=float)
    ts_out_history = np.zeros(num_steps, dtype=float)
    tgr_avg_history = np.zeros(num_steps, dtype=float)
    tgr_max_history = np.zeros(num_steps, dtype=float)
    sd_int_history = np.zeros(num_steps, dtype=float)
    k_history = np.zeros(num_steps, dtype=float)
    event_rho_history_pcm = np.zeros(num_steps, dtype=float)

    diagnostics = {
        "hx1_hot_in": np.zeros(num_steps, dtype=float),
        "hx1_hot_out": np.zeros(num_steps, dtype=float),
        "hx1_cold_in": np.zeros(num_steps, dtype=float),
        "hx1_cold_out": np.zeros(num_steps, dtype=float),
        "hx2_hot_in": np.zeros(num_steps, dtype=float),
        "hx2_hot_out": np.zeros(num_steps, dtype=float),
        "hx2_cold_in": np.zeros(num_steps, dtype=float),
        "hx2_cold_out": np.zeros(num_steps, dtype=float),
        "brayton_T1": np.zeros(num_steps, dtype=float),
        "brayton_T2": np.zeros(num_steps, dtype=float),
        "brayton_T2r": np.zeros(num_steps, dtype=float),
        "brayton_T3": np.zeros(num_steps, dtype=float),
        "brayton_T4": np.zeros(num_steps, dtype=float),
        "brayton_T4r": np.zeros(num_steps, dtype=float),
        "brayton_W_c": np.zeros(num_steps, dtype=float),
        "brayton_W_t": np.zeros(num_steps, dtype=float),
        "brayton_W_net": np.zeros(num_steps, dtype=float),
        "brayton_Q_in": np.zeros(num_steps, dtype=float),
        "brayton_Q_out": np.zeros(num_steps, dtype=float),
        "brayton_eta": np.zeros(num_steps, dtype=float),
    }
    history = {field: [] for field in record_fields}

    phi_1 = np.asarray(params["phi_1_0"], dtype=float).copy()
    phi_2 = np.asarray(params["phi_2_0"], dtype=float).copy()
    precursors = np.asarray(params["c0_groups"], dtype=float).copy()
    sd_profile = np.sum(np.asarray(params["lambda_i_np"], dtype=float)[:, None] * precursors, axis=0)
    q_prime = np.zeros(n, dtype=float)

    for step, current_time in enumerate(time_s):
        history_step = step + history_step_offset
        event_state = build_event_state(current_time, base_ts_in, event_sequence)

        # Match the monolithic kernel's cross-step staging:
        # these three boundaries are stored in state at the end of BOP(k-1)
        # and only injected into the transport channels at step k.
        channels["hx_c"].submit(history_step, carry_bop_feedback["ts_hx1_0"])
        channels["r_hx"].submit(history_step, carry_bop_feedback["tss_hx2_0"])
        channels["pp_r"].submit(history_step, carry_bop_feedback["tsss_pp_0"])

        bop_outputs = {}
        core_outputs = {}

        def run_bop():
            nonlocal y_hx1, y_hx2

            ts_hx1_l = channels["c_hx"].read(history_step, base_ts_out)
            tss_hx1_0 = channels["r_hx"].read(history_step, base_tss_in)
            y_hx1 = HX1(y_hx1[:, -1], ts_hx1_l, tss_hx1_0, params, history_step)
            hx1_hot = np.asarray(y_hx1[:nx, -1], dtype=float)
            hx1_cold = np.asarray(y_hx1[nx:, -1], dtype=float)
            ts_hx1_0 = float(hx1_hot[0])
            tss_hx1_l = float(hx1_cold[-1])

            tss_hx2_l = channels["hx_r"].read(history_step, base_tss_out)
            tsss_hx2_0 = channels["pp_r"].read(history_step, base_tsss_in)
            y_hx2 = HX2(y_hx2[:, -1], tss_hx2_l, tsss_hx2_0, params, history_step)
            hx2_hot = np.asarray(y_hx2[:nx, -1], dtype=float)
            hx2_cold = np.asarray(y_hx2[nx:, -1], dtype=float)
            tss_hx2_0 = float(hx2_hot[0])
            tsss_hx2_l = float(hx2_cold[-1])

            channels["hx_r"].submit(history_step, tss_hx1_l)
            channels["r_pp"].submit(history_step, tsss_hx2_l)

            tsss_pp_l = channels["r_pp"].read(history_step, base_tsss_out)
            tsss_pp_0 = float(power_plant_temp(tsss_pp_l, params, history_step))

            carry_bop_feedback["ts_hx1_0"] = ts_hx1_0
            carry_bop_feedback["tss_hx2_0"] = tss_hx2_0
            carry_bop_feedback["tsss_pp_0"] = tsss_pp_0

            bop_outputs.update(
                {
                    "hx1_hot": hx1_hot,
                    "hx1_cold": hx1_cold,
                    "hx2_hot": hx2_hot,
                    "hx2_cold": hx2_cold,
                    "ts_hx1_l": ts_hx1_l,
                    "ts_hx1_0": ts_hx1_0,
                    "tss_hx1_0": tss_hx1_0,
                    "tss_hx1_l": tss_hx1_l,
                    "tss_hx2_l": tss_hx2_l,
                    "tss_hx2_0": tss_hx2_0,
                    "tsss_hx2_0": tsss_hx2_0,
                    "tsss_hx2_l": tsss_hx2_l,
                    "tsss_pp_l": tsss_pp_l,
                    "tsss_pp_0": tsss_pp_0,
                }
            )

        def run_core():
            nonlocal y_n, y_th, temperature_fuel, temperature_graphite
            nonlocal phi_1, phi_2, precursors, sd_profile, q_prime

            if params.get("core_inlet_mode", "hx_coupled") == "hx_coupled":
                ts_core_0 = channels["hx_c"].read(history_step, event_state["core_inlet_temperature"])
            else:
                ts_core_0 = float(event_state["core_inlet_temperature"])

            neutronics_state = {
                "temperature_fuel": temperature_fuel,
                "temperature_graphite": temperature_graphite,
                "rod_position": event_state["rod_position"],
                "external_reactivity": event_state["external_reactivity"],
            }
            y_n, q_prime_out = neutronics(y_n[:, -1], neutronics_state, history_step, params)
            phi_1_out, phi_2_out, precursors_out = _extract_state(y_n[:, -1], n, params["precursor_groups"])
            y_th = thermal_hydraulics(y_th[:, -1], q_prime_out, ts_core_0, params, step)
            temperature_fuel_out = np.asarray(y_th[:n, -1], dtype=float)
            temperature_graphite_out = np.asarray(y_th[n:, -1], dtype=float)
            ts_core_l = float(temperature_fuel_out[-1])

            channels["c_hx"].submit(history_step, ts_core_l)

            xs_source = params["last_cross_sections"]
            fission_source = xs_source["nu_sigma_f"][0] * phi_1_out + xs_source["nu_sigma_f"][1] * phi_2_out
            sd_profile_out = np.sum(
                np.asarray(params["lambda_i_np"], dtype=float)[:, None] * precursors_out,
                axis=0,
            )

            phi_1 = np.asarray(phi_1_out, dtype=float)
            phi_2 = np.asarray(phi_2_out, dtype=float)
            precursors = np.asarray(precursors_out, dtype=float)
            sd_profile = np.asarray(sd_profile_out, dtype=float)
            q_prime = np.asarray(q_prime_out, dtype=float)
            temperature_fuel = np.asarray(temperature_fuel_out, dtype=float)
            temperature_graphite = np.asarray(temperature_graphite_out, dtype=float)

            core_outputs.update(
                {
                    "phi_1": phi_1,
                    "phi_2": phi_2,
                    "precursors": precursors,
                    "q_prime": q_prime,
                    "fission_source": fission_source,
                    "ts_core_0": ts_core_0,
                    "ts_core_l": ts_core_l,
                    "temperature_fuel": temperature_fuel,
                    "temperature_graphite": temperature_graphite,
                }
            )

        if execution_order == "core_then_bop":
            run_core()
            run_bop()
        else:
            run_bop()
            run_core()

        xs_diag = build_cross_sections(
            temperature_fuel=temperature_fuel,
            temperature_graphite=temperature_graphite,
            params=params,
            rod_position=event_state["rod_position"],
            external_reactivity=event_state["external_reactivity"],
        )
        if diagnostic_mode == "eigenvalue":
            diag = compute_reactivity_from_xs(xs_diag, params, reference_k_raw, phi_guess=phi_guess)
            phi_guess = diag["phi"]
            rho_history_pcm[step] = 1.0e5 * diag["rho"]
            k_history[step] = diag["k_eff_global"]
        else:
            rho_history_pcm[step] = 1.0e5 * float(params["last_global_rho"])
            k_history[step] = 1.0 / max(1.0 - float(params["last_global_rho"]), 1.0e-12)

        power_history[step] = trapz(q_prime, z)
        ts_in_history[step] = core_outputs["ts_core_0"]
        ts_out_history[step] = core_outputs["ts_core_l"]
        tgr_avg_history[step] = trapz(temperature_graphite, z) / max(z[-1] - z[0], 1.0e-12)
        tgr_max_history[step] = float(np.max(temperature_graphite))
        sd_int_history[step] = trapz(sd_profile, z)
        event_rho_history_pcm[step] = float(event_state["external_reactivity"] * 1.0e5)

        diagnostics["hx1_hot_in"][step] = bop_outputs["ts_hx1_l"]
        diagnostics["hx1_hot_out"][step] = bop_outputs["ts_hx1_0"]
        diagnostics["hx1_cold_in"][step] = bop_outputs["tss_hx1_0"]
        diagnostics["hx1_cold_out"][step] = bop_outputs["tss_hx1_l"]
        diagnostics["hx2_hot_in"][step] = bop_outputs["tss_hx2_l"]
        diagnostics["hx2_hot_out"][step] = bop_outputs["tss_hx2_0"]
        diagnostics["hx2_cold_in"][step] = bop_outputs["tsss_hx2_0"]
        diagnostics["hx2_cold_out"][step] = bop_outputs["tsss_hx2_l"]

        pp_state = params.get("last_power_plant", {})
        for key in ("T1", "T2", "T2r", "T3", "T4", "T4r", "W_c", "W_t", "W_net", "Q_in", "Q_out", "eta_b"):
            if key not in pp_state:
                continue
            target = "brayton_eta" if key == "eta_b" else f"brayton_{key}"
            diagnostics[target][step] = float(pp_state[key])

        record_map = {
            "phi1": phi_1,
            "phi2": phi_2,
            "C": precursors,
            "Sd": sd_profile,
            "Ts": temperature_fuel,
            "Tgr": temperature_graphite,
            "F": core_outputs["fission_source"],
            "qprime": q_prime,
            "HX1_hot": bop_outputs["hx1_hot"],
            "HX1_cold": bop_outputs["hx1_cold"],
            "HX2_hot": bop_outputs["hx2_hot"],
            "HX2_cold": bop_outputs["hx2_cold"],
        }
        for field in record_fields:
            history[field].append(np.asarray(record_map[field], dtype=float).copy())

    for field, entries in history.items():
        history[field] = np.asarray(entries, dtype=float)

    return {
        "time_s": time_s,
        "z": z,
        "power_W": power_history,
        "rho_pcm": rho_history_pcm,
        "k_eff_global": k_history,
        "Ts_in_K": ts_in_history,
        "Ts_out_K": ts_out_history,
        "Tgr_avg_K": tgr_avg_history,
        "Tgr_max_K": tgr_max_history,
        "Sd_int": sd_int_history,
        "external_rho_pcm": event_rho_history_pcm,
        "diagnostics": diagnostics,
        "history": history,
        "event_sequence": event_sequence or [],
        "final_phi1": np.asarray(phi_1, dtype=float),
        "final_phi2": np.asarray(phi_2, dtype=float),
        "final_C": np.asarray(precursors, dtype=float),
        "final_Sd": np.asarray(sd_profile, dtype=float),
        "final_Ts": np.asarray(temperature_fuel, dtype=float),
        "final_Tgr": np.asarray(temperature_graphite, dtype=float),
        "reference_k_raw": reference_k_raw,
        "execution_order": execution_order,
    }


def _linf_diff(lhs, rhs):
    return float(np.max(np.abs(np.asarray(lhs, dtype=float) - np.asarray(rhs, dtype=float))))


def compare_async_split_against_reference(
    params,
    num_steps,
    event_sequence=None,
    diagnostic_mode="eigenvalue",
    execution_order="bop_then_core",
):
    reference = run_coupled_transient(
        copy.deepcopy(params),
        num_steps,
        event_sequence=event_sequence,
        record_fields={"C", "HX1_hot", "HX1_cold", "HX2_hot", "HX2_cold", "Ts", "Tgr", "qprime"},
        diagnostic_mode=diagnostic_mode,
    )
    split = run_async_split_transient(
        copy.deepcopy(params),
        num_steps,
        event_sequence=event_sequence,
        record_fields={"C", "HX1_hot", "HX1_cold", "HX2_hot", "HX2_cold", "Ts", "Tgr", "qprime"},
        diagnostic_mode=diagnostic_mode,
        execution_order=execution_order,
    )

    max_abs = {
        "power_W": _linf_diff(reference["power_W"], split["power_W"]),
        "rho_pcm": _linf_diff(reference["rho_pcm"], split["rho_pcm"]),
        "Ts_in_K": _linf_diff(reference["Ts_in_K"], split["Ts_in_K"]),
        "Ts_out_K": _linf_diff(reference["Ts_out_K"], split["Ts_out_K"]),
        "hx1_hot_out": _linf_diff(reference["diagnostics"]["hx1_hot_out"], split["diagnostics"]["hx1_hot_out"]),
        "hx1_cold_out": _linf_diff(reference["diagnostics"]["hx1_cold_out"], split["diagnostics"]["hx1_cold_out"]),
        "hx2_hot_out": _linf_diff(reference["diagnostics"]["hx2_hot_out"], split["diagnostics"]["hx2_hot_out"]),
        "hx2_cold_out": _linf_diff(reference["diagnostics"]["hx2_cold_out"], split["diagnostics"]["hx2_cold_out"]),
        "brayton_eta": _linf_diff(reference["diagnostics"]["brayton_eta"], split["diagnostics"]["brayton_eta"]),
    }
    final_state_linf = {
        "phi1": _linf_diff(reference["final_phi1"], split["final_phi1"]),
        "phi2": _linf_diff(reference["final_phi2"], split["final_phi2"]),
        "C": _linf_diff(reference["final_C"], split["final_C"]),
        "Ts": _linf_diff(reference["final_Ts"], split["final_Ts"]),
        "Tgr": _linf_diff(reference["final_Tgr"], split["final_Tgr"]),
    }
    history_linf = {
        "qprime": _linf_diff(reference["history"]["qprime"], split["history"]["qprime"]),
        "HX1_hot": _linf_diff(reference["history"]["HX1_hot"], split["history"]["HX1_hot"]),
        "HX2_hot": _linf_diff(reference["history"]["HX2_hot"], split["history"]["HX2_hot"]),
        "Ts": _linf_diff(reference["history"]["Ts"], split["history"]["Ts"]),
        "Tgr": _linf_diff(reference["history"]["Tgr"], split["history"]["Tgr"]),
    }

    return {
        "execution_order": execution_order,
        "max_abs": max_abs,
        "final_state_linf": final_state_linf,
        "history_linf": history_linf,
    }


def main():
    parser = argparse.ArgumentParser(description="Prototype CPU-brokered async split scheduler.")
    parser.add_argument("--steps", type=int, default=24, help="Number of outer steps to simulate.")
    parser.add_argument(
        "--order",
        choices=("core_then_bop", "bop_then_core"),
        default="bop_then_core",
        help="Per-step execution order for the split solver.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    params = generate_parameters()
    summary = compare_async_split_against_reference(
        params=params,
        num_steps=args.steps,
        execution_order=args.order,
    )

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    print(f"execution_order={summary['execution_order']}")
    print("max_abs:")
    for key, value in summary["max_abs"].items():
        print(f"  {key}: {value:.6e}")
    print("final_state_linf:")
    for key, value in summary["final_state_linf"].items():
        print(f"  {key}: {value:.6e}")
    print("history_linf:")
    for key, value in summary["history_linf"].items():
        print(f"  {key}: {value:.6e}")


if __name__ == "__main__":
    main()
