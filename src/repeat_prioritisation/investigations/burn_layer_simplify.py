"""How much does the map simplification change the burned-area layer drawn on the dashboard?

  python -m repeat_prioritisation.investigations.burn_layer_simplify --config configs/examples/national_profile.yaml KHG.16.02.01 [...]

The dashboard map draws the burnt-area polygons of a KHG, merged by number of burns (1, 2, 3, 4+), simplified with the
tolerance of `national.dashboard.profile_layers`. The ranking and the land-status tables never use these shapes: they count
grid points. This script prints, per KHG and burn class, the exact area (equal-area projection) and the area of the drawn shape.
"""
import argparse
from pathlib import Path

import numpy as np
import shapely

from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("khg", nargs="+")
    a = ap.parse_args(argv)
    cfg = L.load_cfg(a.config)
    khg = P.load_khg(cfg).set_index("khg_id")
    data, inp = Path(cfg["data"]), cfg["inputs"]
    ycols = [f"BA_{y}" for y in range(2015, 2026)]
    for kid in a.khg:
        g = shapely.make_valid(khg.loc[kid].geometry)
        km2 = O.to_aea(g).area / 1e6
        tol = 0.0003 + 0.00002 * np.sqrt(km2)
        b = P._read_mask(data / inp["burned"], g, columns=ycols)
        n = b[ycols].notna().sum(axis=1).to_numpy()
        geom = shapely.intersection(shapely.make_valid(b.geometry.values), g)
        print(f"{kid}: {km2:,.0f} km2, {len(b):,} burn polygons, tolerance {tol:.5f} deg (~{tol * 111_000:.0f} m)")
        for k in (1, 2, 3, 4):
            sel = (n == k) if k < 4 else (n >= 4)
            if not sel.any():
                continue
            u = shapely.union_all(geom[sel])
            s = u.simplify(tol, preserve_topology=True)
            ea, sa = O.to_aea(u).area / 1e6, O.to_aea(s).area / 1e6
            print(f"  burned {k}{'+' if k == 4 else 'x'}: exact {ea:9.2f} km2, drawn {sa:9.2f} km2 ({100 * (sa / ea - 1):+.2f}%), "
                  f"vertices {shapely.get_num_coordinates(u):,} -> {shapely.get_num_coordinates(s):,}")


if __name__ == "__main__":
    main()
