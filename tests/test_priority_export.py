"""subkhg_priority.csv: ranks, the KHG-level deficit joined by khg_id, empty columns where nothing is given.

    python -m tests.test_priority_export
"""
import numpy as np
import pandas as pd

from repeat_prioritisation.subkhg.priority_export import priority_table


def _ranked():
    return pd.DataFrame({"unit_id": ["A_S01", "A_S02", "B_S01"], "khg_id": ["A", "A", "B"], "peringkat": [2, 1, 3]})


def test_rank_deficit_and_period():
    nk = pd.DataFrame({"khg_id": ["A", "B"], "deficit_mm": [290.0, 7.0]})
    t = priority_table(_ranked(), nk, 120)
    assert list(t.columns) == ["unit_id", "priority_rank", "deficit_mm", "design_period_days"]
    assert list(t.unit_id) == ["A_S02", "A_S01", "B_S01"] and list(t.priority_rank) == [1, 2, 3]
    assert list(t.deficit_mm) == [290.0, 290.0, 7.0] and (t.design_period_days == 120).all()
    print("ok test_rank_deficit_and_period")


def test_empty_where_nothing_is_given_or_a_khg_is_missing():
    t = priority_table(_ranked())
    assert t.deficit_mm.isna().all() and t.design_period_days.isna().all()
    t = priority_table(_ranked(), pd.DataFrame({"khg_id": ["A"], "deficit_mm": [5.0]}))
    assert t.set_index("unit_id").deficit_mm["A_S01"] == 5.0 and np.isnan(t.set_index("unit_id").deficit_mm["B_S01"])
    print("ok test_empty_where_nothing_is_given_or_a_khg_is_missing")


if __name__ == "__main__":
    test_rank_deficit_and_period()
    test_empty_where_nothing_is_given_or_a_khg_is_missing()
