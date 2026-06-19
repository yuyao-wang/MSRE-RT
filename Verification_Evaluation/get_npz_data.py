#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path

import numpy as np


DEFAULT_DIR = Path(__file__).resolve().parent / "simulation_results"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "neutron_flux_results.csv"


def extract_neutron_flux_results(
    *,
    simulation_dir: Path,
    output_csv: Path,
    start_index: int,
    end_index: int,
    step: int,
    prefix: str,
) -> int:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with output_csv.open(mode="w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Filename", "Step", "Neutron Flux", "Neutron Flux Change"])
        for index in range(start_index, end_index + 1):
            filename = f"{prefix}_{index}.npz"
            filepath = simulation_dir / filename
            if not filepath.exists():
                continue
            data = np.load(filepath, allow_pickle=True)
            for entry in data["data"]:
                if not isinstance(entry, dict) or entry.get("step") != step:
                    continue
                neutron_flux_change = np.asarray(entry["neutron_flux_change"]).reshape(-1)[0]
                writer.writerow([filename, entry["step"], entry["neutron_flux"], neutron_flux_change])
                rows_written += 1
                break
    return rows_written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract selected neutron-flux rows from simulation NPZ files.")
    parser.add_argument("--simulation-dir", type=Path, default=DEFAULT_DIR, help="Directory containing specific_data_*.npz.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path.")
    parser.add_argument("--start-index", type=int, default=0, help="First simulation index to scan.")
    parser.add_argument("--end-index", type=int, default=29, help="Last simulation index to scan, inclusive.")
    parser.add_argument("--step", type=int, default=19999, help="Saved simulation step to extract.")
    parser.add_argument("--prefix", default="specific_data", help="NPZ filename prefix before _<index>.npz.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = extract_neutron_flux_results(
        simulation_dir=args.simulation_dir,
        output_csv=args.output,
        start_index=args.start_index,
        end_index=args.end_index,
        step=args.step,
        prefix=args.prefix,
    )
    print(f"Data extraction complete. Rows written: {rows}. Results saved to {args.output}.")


if __name__ == "__main__":
    main()
