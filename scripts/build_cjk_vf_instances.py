#!/usr/bin/env python3
"""
Pre-generate static font instances from NotoSansCJKsc-VF.ttf.

Outputs: src/report_pipeline/fonts/instances/NotoSansCJKsc-VF-w{weight}.ttf
Default weights: 100,200,...,900
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_instances(vf_path: Path, out_dir: Path, weights: list[int]) -> None:
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    out_dir.mkdir(parents=True, exist_ok=True)
    base = TTFont(str(vf_path))

    if "fvar" not in base:
        raise RuntimeError(f"Not a variable font: {vf_path}")

    axes = {a.axisTag: a for a in base["fvar"].axes}
    wght_axis = axes.get("wght")
    if wght_axis is None:
        raise RuntimeError(f"Font has no wght axis: {vf_path}")

    for w in weights:
        target = min(max(float(w), wght_axis.minValue), wght_axis.maxValue)
        out = out_dir / f"{vf_path.stem}-w{int(w)}.ttf"
        instanced = instancer.instantiateVariableFont(base, {"wght": target}, inplace=False)
        instanced.save(str(out))
        print(f"generated: {out} (wght={int(target)})")


def parse_weights(raw: str) -> list[int]:
    if raw.strip().lower() == "all":
        return [100, 200, 300, 400, 500, 600, 700, 800, 900]
    vals = []
    for part in raw.split(","):
        v = int(part.strip())
        if v <= 0:
            raise ValueError(f"Invalid weight: {v}")
        vals.append(v)
    return vals


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_vf = repo_root / "src" / "report_pipeline" / "fonts" / "NotoSansCJKsc-VF.ttf"
    default_out = repo_root / "src" / "report_pipeline" / "fonts" / "instances"

    parser = argparse.ArgumentParser(description="Build static instances from CJK variable font")
    parser.add_argument("--vf", type=Path, default=default_vf, help="Variable font path")
    parser.add_argument("--out-dir", type=Path, default=default_out, help="Output directory")
    parser.add_argument(
        "--weights",
        default="all",
        help="Comma-separated weights (e.g. 400,700) or 'all' for 100..900",
    )
    args = parser.parse_args()

    weights = parse_weights(args.weights)
    build_instances(args.vf, args.out_dir, weights)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
