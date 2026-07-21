#!/usr/bin/env python3

import argparse
from pathlib import Path

import numpy as np


def read_npz(file_path: Path, *, list_only: bool, max_items: int | None) -> None:
    data = np.load(file_path, allow_pickle=True)
    print("Available arrays in the .npz file:")
    for key in data.files:
        array = data[key]
        print(f"Array name: {key}, Shape: {array.shape}, Dtype: {array.dtype}")
        if list_only:
            continue
        if max_items is None:
            print(array)
        else:
            flat = array.reshape(-1)
            print(flat[:max_items])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect arrays stored in an NPZ file.")
    parser.add_argument("npz_file", type=Path, help="NPZ file to inspect.")
    parser.add_argument("--list-only", action="store_true", help="Only print names, shapes, and dtypes.")
    parser.add_argument("--max-items", type=int, default=None, help="Maximum flattened items to print per array.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    read_npz(args.npz_file, list_only=args.list_only, max_items=args.max_items)


if __name__ == "__main__":
    main()
