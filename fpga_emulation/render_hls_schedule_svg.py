#!/usr/bin/env python3

"""Render a compact SVG from Vivado HLS sched/design XML files."""

from __future__ import annotations

import argparse
import re
import textwrap
import xml.etree.ElementTree as ET
from collections import Counter
from html import escape
from pathlib import Path


CATEGORY_LABELS = {
    "axi_read": "AXI-Lite read",
    "axi_write": "AXI-Lite write",
    "partselect": "PartSelect",
    "spec_interface": "SpecInterface",
    "spec_bits": "SpecBitsMap",
    "spec_top": "SpecTopModule",
    "user_call": "User call",
    "other": "Other",
}


def extract_call_target(node_text: str) -> str | None:
    match = re.search(r"call\s+(?:fastcc\s+)?(?:[^@]+)@([A-Za-z0-9_]+)\(", node_text)
    if not match:
        return None
    callee = match.group(1)
    if callee.startswith("_ssdm_"):
        return None
    return callee


def classify_operation(node_text: str) -> str:
    if "_ssdm_op_Read" in node_text:
        return "axi_read"
    if "_ssdm_op_Write" in node_text:
        return "axi_write"
    if "_ssdm_op_PartSelect" in node_text:
        return "partselect"
    if "_ssdm_op_SpecInterface" in node_text:
        return "spec_interface"
    if "_ssdm_op_SpecBitsMap" in node_text:
        return "spec_bits"
    if "_ssdm_op_SpecTopModule" in node_text:
        return "spec_top"
    if extract_call_target(node_text):
        return "user_call"
    return "other"


def parse_sched(path: Path) -> dict:
    root = ET.parse(path).getroot()
    transitions = []
    for trans in root.findall("./trans_list/trans"):
        transitions.append(
            {
                "id": trans.attrib.get("id", "?"),
                "from": trans.attrib.get("from", "?"),
                "to": trans.attrib.get("to", "?"),
            }
        )

    states = []
    for state in root.findall("./state_list/state"):
        operations = state.findall("operation")
        categories = Counter()
        calls = Counter()
        for op in operations:
            node_text = " ".join((op.findtext("Node") or "").split())
            category = classify_operation(node_text)
            categories[category] += 1
            callee = extract_call_target(node_text)
            if callee:
                calls[callee] += 1
        states.append(
            {
                "id": state.attrib.get("id", "?"),
                "st_id": state.attrib.get("st_id", "?"),
                "op_count": len(operations),
                "categories": categories,
                "calls": calls,
            }
        )

    return {
        "name": root.findtext("name", default=path.stem),
        "transitions": transitions,
        "states": states,
    }


def parse_module(module_el: ET.Element) -> dict:
    resources = {}
    for tag in ("BRAM_18K", "DSP48E", "FF", "LUT", "URAM"):
        resources[tag] = module_el.findtext(f"./AreaEstimates/Resources/{tag}", default="?")

    return {
        "lat_min": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/Best-caseLatency", default="?"
        ),
        "lat_max": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/Worst-caseLatency", default="?"
        ),
        "rt_min": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/Best-caseRealTimeLatency", default="?"
        ),
        "rt_max": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/Worst-caseRealTimeLatency", default="?"
        ),
        "ii": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/PipelineInitiationInterval",
            default="?",
        ),
        "pipeline": module_el.findtext(
            "./PerformanceEstimates/SummaryOfOverallLatency/PipelineType", default="?"
        ),
        "clk": module_el.findtext(
            "./PerformanceEstimates/SummaryOfTimingAnalysis/EstimatedClockPeriod", default="?"
        ),
        "target_clk": module_el.findtext(
            "./PerformanceEstimates/SummaryOfTimingAnalysis/TargetClockPeriod", default="?"
        ),
        "resources": resources,
    }


def parse_instance(instance_el: ET.Element) -> dict:
    children_el = instance_el.find("InstancesList")
    children = []
    if children_el is not None:
        children = [parse_instance(child) for child in children_el.findall("Instance")]
    return {
        "inst_name": instance_el.findtext("InstName", default="?"),
        "module_name": instance_el.findtext("ModuleName", default="?"),
        "children": children,
    }


def parse_design(path: Path) -> dict:
    root = ET.parse(path).getroot()
    modules = {}
    for module_el in root.findall("./ModuleInformation/Module"):
        name = module_el.findtext("Name")
        if name:
            modules[name] = parse_module(module_el)

    top_el = root.find("./RTLDesignHierarchy/TopModule")
    top = None
    if top_el is not None:
        children_el = top_el.find("InstancesList")
        top = {
            "module_name": top_el.findtext("ModuleName", default="?"),
            "children": [parse_instance(child) for child in children_el.findall("Instance")]
            if children_el is not None
            else [],
        }

    return {"modules": modules, "top": top}


def format_latency(info: dict | None) -> str:
    if not info:
        return "? cyc"
    lat_min = info.get("lat_min", "?")
    lat_max = info.get("lat_max", "?")
    if lat_min == lat_max:
        return f"{lat_min} cyc"
    return f"{lat_min}..{lat_max} cyc"


def format_clock(info: dict | None) -> str:
    if not info:
        return "? ns"
    return f"{info.get('clk', '?')} ns"


def format_resources(info: dict | None) -> str:
    if not info:
        return "BRAM=? DSP=? FF=? LUT=?"
    resources = info.get("resources", {})
    return (
        f"BRAM={resources.get('BRAM_18K', '?')} "
        f"DSP={resources.get('DSP48E', '?')} "
        f"FF={resources.get('FF', '?')} "
        f"LUT={resources.get('LUT', '?')}"
    )


def hierarchy_lines(top: dict | None, modules: dict) -> list[str]:
    if not top:
        return []

    lines = []

    def walk(node: dict, depth: int) -> None:
        module_name = node["module_name"]
        info = modules.get(module_name)
        prefix = "  " * depth + "- "
        lines.append(f"{prefix}{module_name} | {format_latency(info)} @ {format_clock(info)}")
        for child in node.get("children", []):
            walk(child, depth + 1)

    walk(top, 0)
    return lines


def state_lines(state: dict) -> list[str]:
    lines = [f"State {state['id']} (st_id={state['st_id']})", f"{state['op_count']} operations"]

    for category, count in state["categories"].most_common():
        label = CATEGORY_LABELS.get(category, category)
        lines.append(f"{label} x{count}")
        if len(lines) >= 6:
            break

    if state["calls"]:
        rendered_calls = ", ".join(f"{name} x{count}" for name, count in state["calls"].items())
        lines.append(f"calls {rendered_calls}")

    return lines[:7]


def wrap_text_lines(lines: list[str], width: int) -> list[str]:
    wrapped = []
    for line in lines:
        chunks = textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False)
        wrapped.extend(chunks or [""])
    return wrapped


def render_svg(schedule: dict, design: dict, out_path: Path) -> None:
    top_info = design["modules"].get(schedule["name"])
    hierarchy = hierarchy_lines(design.get("top"), design["modules"])

    title_lines = [
        schedule["name"],
        (
            f"latency {format_latency(top_info)} | abs {top_info.get('rt_min', '?')}.."
            f"{top_info.get('rt_max', '?')} | est clk {format_clock(top_info)}"
            if top_info
            else "latency ? | est clk ?"
        ),
        (
            f"II {top_info.get('ii', '?')} | pipeline {top_info.get('pipeline', '?')} | "
            f"{format_resources(top_info)}"
            if top_info
            else "II ? | pipeline ? | BRAM=? DSP=? FF=? LUT=?"
        ),
    ]

    wrapped_state_blocks = [wrap_text_lines(state_lines(state), 32) for state in schedule["states"]]
    wrapped_hierarchy = wrap_text_lines(hierarchy, 110) if hierarchy else ["Hierarchy unavailable"]

    margin = 24
    panel_padding = 16
    title_height = 120
    box_width = 310
    box_gap = 36
    line_height = 18
    state_box_height = max(120, max(len(block) for block in wrapped_state_blocks) * line_height + 34)
    state_area_height = state_box_height + 64
    hierarchy_height = len(wrapped_hierarchy) * line_height + 42
    width = max(1180, margin * 2 + len(wrapped_state_blocks) * box_width + (len(wrapped_state_blocks) - 1) * box_gap)
    height = margin * 2 + title_height + state_area_height + hierarchy_height

    state_y = margin + title_height + 24
    hierarchy_y = state_y + state_area_height

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    svg.append(
        "<defs>"
        "<marker id=\"arrow\" viewBox=\"0 0 10 10\" refX=\"9\" refY=\"5\" "
        "markerWidth=\"7\" markerHeight=\"7\" orient=\"auto-start-reverse\">"
        "<path d=\"M 0 0 L 10 5 L 0 10 z\" fill=\"#3b4a6b\"/>"
        "</marker>"
        "</defs>"
    )
    svg.append('<rect width="100%" height="100%" fill="#f7f8fc"/>')

    svg.append(
        f'<rect x="{margin}" y="{margin}" width="{width - 2 * margin}" height="{title_height}" '
        'rx="18" fill="#e9eef9" stroke="#c7d3ec"/>'
    )
    for idx, line in enumerate(title_lines):
        font_size = 22 if idx == 0 else 16
        font_weight = "700" if idx == 0 else "400"
        svg.append(
            f'<text x="{margin + panel_padding}" y="{margin + 34 + idx * 28}" '
            f'font-family="Menlo, Consolas, monospace" font-size="{font_size}" '
            f'font-weight="{font_weight}" fill="#1f2940">{escape(line)}</text>'
        )

    centers = {}
    for idx, block in enumerate(wrapped_state_blocks):
        x = margin + idx * (box_width + box_gap)
        centers[schedule["states"][idx]["id"]] = x + box_width / 2
        fill = "#fffdf4" if idx == 0 else "#ffffff"
        svg.append(
            f'<rect x="{x}" y="{state_y}" width="{box_width}" height="{state_box_height}" '
            f'rx="16" fill="{fill}" stroke="#b8c3db" stroke-width="1.5"/>'
        )
        for line_idx, line in enumerate(block):
            font_size = 16 if line_idx == 0 else 14
            font_weight = "700" if line_idx == 0 else "400"
            svg.append(
                f'<text x="{x + 18}" y="{state_y + 28 + line_idx * line_height}" '
                f'font-family="Menlo, Consolas, monospace" font-size="{font_size}" '
                f'font-weight="{font_weight}" fill="#23304d">{escape(line)}</text>'
            )

    arrow_y = state_y + state_box_height / 2
    for trans in schedule["transitions"]:
        start_x = centers.get(trans["from"])
        end_x = centers.get(trans["to"])
        if start_x is None or end_x is None:
            continue
        start_x += box_width / 2 - 6
        end_x -= box_width / 2 - 6
        svg.append(
            f'<line x1="{start_x}" y1="{arrow_y}" x2="{end_x}" y2="{arrow_y}" '
            'stroke="#3b4a6b" stroke-width="2" marker-end="url(#arrow)"/>'
        )
        mid_x = (start_x + end_x) / 2
        svg.append(
            f'<text x="{mid_x}" y="{arrow_y - 10}" text-anchor="middle" '
            'font-family="Menlo, Consolas, monospace" font-size="13" fill="#46557b">'
            f'{escape("t" + trans["id"])}'
            "</text>"
        )

    svg.append(
        f'<rect x="{margin}" y="{hierarchy_y}" width="{width - 2 * margin}" height="{hierarchy_height}" '
        'rx="18" fill="#ffffff" stroke="#c7d3ec"/>'
    )
    svg.append(
        f'<text x="{margin + panel_padding}" y="{hierarchy_y + 28}" '
        'font-family="Menlo, Consolas, monospace" font-size="18" font-weight="700" '
        'fill="#1f2940">Hierarchy / module latency</text>'
    )
    for idx, line in enumerate(wrapped_hierarchy):
        svg.append(
            f'<text x="{margin + panel_padding}" y="{hierarchy_y + 52 + idx * line_height}" '
            'font-family="Menlo, Consolas, monospace" font-size="14" fill="#23304d">'
            f"{escape(line)}</text>"
        )

    svg.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sched", required=True, type=Path, help="Path to *.sched.adb.xml")
    parser.add_argument("--design", required=True, type=Path, help="Path to *.design.xml")
    parser.add_argument("--out", required=True, type=Path, help="Output SVG path")
    args = parser.parse_args()

    schedule = parse_sched(args.sched)
    design = parse_design(args.design)
    render_svg(schedule, design, args.out)


if __name__ == "__main__":
    main()
