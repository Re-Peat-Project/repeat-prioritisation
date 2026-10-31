#!/usr/bin/env python3
"""Vector tiles of the dashboard map layers: one PMTiles archive for every profiled KHG.

  repeat-national-tiles --config configs/examples/national_profile.yaml [--image repeat-tippecanoe:2.79.0]

`repeat-national-dashboard` writes one GeoJSON-lines file per layer to <out>/tiles/src/ (burn, peat, outline, canal_p, canal_s,
canal_t, forest, feg, licence, ring, village, dmpg); every feature carries `k`, the khg_id. This command turns them into
<out>/khg_layers.pmtiles with tippecanoe (pinned in tiles/Dockerfile; build the image once with
`docker build -t repeat-tippecanoe:2.79.0 repeat-prioritisation/tiles`). No feature is dropped and tiles have no size limit;
lines and polygons are thinned only to the pixel of each zoom level. Serve the archive next to dashboard.html over HTTP
(PMTiles reads byte ranges; a page opened as a file cannot).
"""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
from pathlib import Path

import yaml

from repeat_prioritisation.national import profile as P

IMAGE = "repeat-tippecanoe:2.79.0"
MINZOOM, MAXZOOM = 6, 15    # a z15 tile holds 0.3 m coordinates; the page overzooms from there
FLAGS = ["--force", "-Z", str(MINZOOM), "-z", str(MAXZOOM), "--no-feature-limit", "--no-tile-size-limit", "--no-tiny-polygon-reduction",
         "--read-parallel", "--buffer", "16"]


def write_sources(src, feats):
    """One GeoJSON-lines file per layer; removes files of layers that no longer exist."""
    src = Path(src)
    src.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.geojsonl"):
        f.unlink()
    for layer, rows in feats.items():
        (src / f"{layer}.geojsonl").write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def run(out_dir, image=IMAGE):
    out_dir = Path(out_dir)
    src = out_dir / "tiles" / "src"
    files = sorted(src.glob("*.geojsonl"))
    if not files:
        raise SystemExit(f"no tile sources in {src}: run repeat-national-dashboard first")
    target = out_dir / "khg_layers.pmtiles"
    cmd = ["docker", "run", "--rm", "-v", f"{src.resolve()}:/in:ro", "-v", f"{out_dir.resolve()}:/out", image,
           "-o", "/out/khg_layers.pmtiles", *FLAGS, *[a for f in files for a in ("-L", f"{f.stem}:/in/{f.name}")]]
    subprocess.run(cmd, check=True)
    print(f"{target}: {target.stat().st_size / 1e6:.1f} MB, layers {', '.join(f.stem for f in files)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--image", default=IMAGE)
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    run(P._expand(cfg)["out"], a.image)


if __name__ == "__main__":
    main()
