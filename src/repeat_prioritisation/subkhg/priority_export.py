"""subkhg_priority.csv: the table `repeat-pump` reads (contract C6 in re-peat/docs/11-data-contracts.md).

    unit_id, priority_rank, deficit_mm, design_period_days

priority_rank is `peringkat` of the ranking (1 = most need). deficit_mm is the KHG-level deficit of neraca air (`neraca_khg.csv` of
repeat-neraca), the same value for every unit of a KHG until neraca has spatial skill. design_period_days comes from the config. Any column
may be empty: the pump module then falls back to equal priority and specific-yield demand, and says so.

Config (`priority_export:`):
    neraca_khg: path to neraca_khg.csv, or null          the deficit_mm of the row whose khg_id matches the unit's khg_id
    design_period_days: number or null                   days over which the water has to be delivered
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("prioritas.priority_export")

EXPORT_DEFAULTS = {"neraca_khg": None, "design_period_days": None}


def priority_table(ranked: pd.DataFrame, neraca_khg: pd.DataFrame | None = None, design_period_days: float | None = None) -> pd.DataFrame:
    """unit_id, priority_rank, deficit_mm, design_period_days for the ranked units (needs unit_id, khg_id, peringkat)."""
    t = pd.DataFrame({"unit_id": ranked["unit_id"].astype(str).values, "priority_rank": ranked["peringkat"].values})
    deficit = np.full(len(t), np.nan)
    if neraca_khg is not None:
        d = neraca_khg.assign(khg_id=neraca_khg["khg_id"].astype(str)).drop_duplicates("khg_id").set_index("khg_id")["deficit_mm"]
        deficit = ranked["khg_id"].astype(str).map(d).values.astype(float)
        missing = sorted(set(ranked["khg_id"].astype(str)) - set(d.index))
        if missing:
            log.warning("neraca_khg.csv has no row for khg_id %s: their deficit_mm is empty", ", ".join(missing))
    t["deficit_mm"] = deficit
    t["design_period_days"] = np.nan if design_period_days is None else float(design_period_days)
    return t.sort_values("priority_rank").reset_index(drop=True)


def write_priority(gdf, cfg: dict, out: Path) -> None:
    """Hook for pipeline.main (`after`): writes <out>/subkhg_priority.csv."""
    c = {**EXPORT_DEFAULTS, **(cfg.get("priority_export") or {})}
    nk = pd.read_csv(c["neraca_khg"]) if c["neraca_khg"] else None
    t = priority_table(pd.DataFrame(gdf.drop(columns="geometry", errors="ignore")), nk, c["design_period_days"])
    t.to_csv(Path(out) / "subkhg_priority.csv", index=False, float_format="%.3f")
    log.info("subkhg_priority.csv: %d units, deficit_mm %s, design_period_days %s", len(t),
             "from " + str(c["neraca_khg"]) if nk is not None else "empty", c["design_period_days"])
