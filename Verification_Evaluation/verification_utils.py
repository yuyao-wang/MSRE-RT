import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

WORKSPACE_ROOT = Path(__file__).resolve().parent
MPL_CACHE_DIR = WORKSPACE_ROOT / ".mplconfig"
FONT_CACHE_DIR = WORKSPACE_ROOT / ".cache"
MPL_CACHE_DIR.mkdir(exist_ok=True)
FONT_CACHE_DIR.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(FONT_CACHE_DIR))

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover - optional plotting dependency
    vendor_path = Path(__file__).resolve().parent / ".vendor"
    if vendor_path.exists():
        sys.path.insert(0, str(vendor_path))
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            matplotlib = None
            plt = None
    else:
        matplotlib = None
        plt = None


DEFAULT_STYLE = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 20,
    "font.weight": "semibold",
    "axes.labelsize": 24,
    "axes.titlesize": 24,
    "axes.labelweight": "semibold",
    "xtick.labelsize": 19,
    "ytick.labelsize": 19,
    "legend.fontsize": 18,
    "figure.dpi": 220,
    "savefig.dpi": 600,
    "axes.linewidth": 1.6,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "grid.linewidth": 1.0,
    "lines.linewidth": 3.2,
    "lines.markersize": 10,
    "xtick.major.width": 1.4,
    "ytick.major.width": 1.4,
    "xtick.major.size": 6.0,
    "ytick.major.size": 6.0,
    "legend.handlelength": 2.6,
    "legend.handletextpad": 0.8,
}


def apply_publication_style():
    if plt is None:
        return
    plt.rcParams.update(DEFAULT_STYLE)


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def write_csv(path, fieldnames, rows):
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path, payload):
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)


def iso_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def save_figure(fig, stem):
    if plt is None:
        raise RuntimeError("matplotlib is required to save figures.")
    stem = Path(stem)
    ensure_dir(stem.parent)
    fig.savefig(f"{stem}.png", bbox_inches="tight", dpi=600)
    fig.savefig(f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def trapz(y, x):
    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(y, x))
    return float(np.trapz(y, x))


def normalize_profile(values):
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    if not np.any(finite):
        return np.full_like(values, np.nan)
    scale = np.nanmax(np.abs(values[finite]))
    if scale <= 0.0:
        return np.zeros_like(values)
    return values / scale


def safe_relative(values, reference, eps=1.0e-12):
    values = np.asarray(values, dtype=float)
    reference = np.asarray(reference, dtype=float)
    return np.abs(values - reference) / np.maximum(np.abs(reference), eps)


def l2_relative_error(values, reference, eps=1.0e-12):
    values = np.asarray(values, dtype=float)
    reference = np.asarray(reference, dtype=float)
    denom = np.linalg.norm(reference.ravel())
    return float(np.linalg.norm((values - reference).ravel()) / max(denom, eps))


def linf_relative_error(values, reference, eps=1.0e-12):
    values = np.asarray(values, dtype=float)
    reference = np.asarray(reference, dtype=float)
    denom = np.max(np.abs(reference))
    return float(np.max(np.abs(values - reference)) / max(denom, eps))


def max_abs_error(values, reference):
    values = np.asarray(values, dtype=float)
    reference = np.asarray(reference, dtype=float)
    return float(np.max(np.abs(values - reference)))


def peak_location(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if not np.any(finite):
        return float("nan")
    x_finite = x[finite]
    y_finite = y[finite]
    ymax = float(np.nanmax(y_finite))
    tol = max(1.0e-12, 1.0e-6 * max(abs(ymax), 1.0))
    indices = np.where(y_finite >= ymax - tol)[0]
    return float(x_finite[int(indices[-1])])


def pcm(rho):
    return 1.0e5 * np.asarray(rho, dtype=float)


def settling_time(time_s, values, band=0.02):
    time_s = np.asarray(time_s, dtype=float)
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan")
    final_value = values[-1]
    tolerance = band * max(abs(final_value), 1.0e-12)
    mask = np.abs(values - final_value) <= tolerance
    for index in range(values.size):
        if np.all(mask[index:]):
            return float(time_s[index])
    return float(time_s[-1])


def interpolate_reference_profile(z_over_h, reference_points):
    z_over_h = np.asarray(z_over_h, dtype=float)
    reference_points = np.asarray(reference_points, dtype=float)
    if reference_points.size == 0:
        return np.full_like(z_over_h, np.nan)

    order = np.argsort(reference_points[:, 0])
    xp = reference_points[order, 0]
    yp = reference_points[order, 1]
    xp = (xp - xp.min()) / max(xp.max() - xp.min(), 1.0e-12)
    return np.interp(z_over_h, xp, yp, left=yp[0], right=yp[-1])


def load_dnp_reference_from_notebook(path="plot.ipynb"):
    notebook_path = Path(path)
    if not notebook_path.exists():
        return {}

    with notebook_path.open() as stream:
        notebook = json.load(stream)

    for cell in notebook.get("cells", []):
        source = "".join(cell.get("source", []))
        if "ref_points" not in source or "np.array" not in source:
            continue
        head = source.split("colors =", 1)[0]
        filtered_lines = []
        for line in head.splitlines():
            stripped = line.strip()
            if stripped.startswith("import pandas"):
                continue
            if stripped.startswith("import matplotlib"):
                continue
            filtered_lines.append(line)
        head = "\n".join(filtered_lines)
        namespace = {"np": np}
        try:
            exec(head, namespace)
        except Exception:
            continue
        ref_points = namespace.get("ref_points")
        if isinstance(ref_points, dict) and ref_points:
            return {key: np.asarray(value, dtype=float) for key, value in ref_points.items()}
    return {}


def plotting_available():
    return plt is not None


def nan_rows(fieldnames, count):
    rows = []
    for _ in range(int(count)):
        rows.append({name: np.nan for name in fieldnames})
    return rows


def parse_csv_value(value):
    if value is None:
        return np.nan
    text = value.strip()
    if text == "":
        return np.nan
    lower = text.lower()
    if lower in {"nan", "none"}:
        return np.nan
    try:
        return float(text)
    except ValueError:
        return text


def read_csv_rows(path):
    path = Path(path)
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        return [{key: parse_csv_value(value) for key, value in row.items()} for row in reader]


def float_column(rows, key):
    return np.asarray([float(row[key]) for row in rows], dtype=float)


def string_column(rows, key):
    return [str(row[key]) for row in rows]


def unique_strings(rows, key):
    seen = []
    for value in string_column(rows, key):
        if value not in seen:
            seen.append(value)
    return seen
