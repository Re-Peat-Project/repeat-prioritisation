"""The neraca air balance columns are used only where repeat_neraca.balance found the order of sub-KHG stable."""
import numpy as np
import pandas as pd

from common.pipeline import gate_balance, merge_indicators


def test_unstable_balance_is_blanked_and_stable_or_khg_level_kept():
    df = pd.DataFrame({"unit_id": ["a", "b", "c"], "u_wb_mean": [1.0, 2.0, 3.0], "u_deficit_months": [1.0, 1.0, 1.0], "u_ndvi": [0.5, 0.6, 0.7]})
    table = pd.DataFrame({"unit_id": ["a", "b", "c"], "u_wb_mean": [10.0, 20.0, 30.0], "u_deficit_months": [2.0, 3.0, 4.0],
                          "balance_stable_ok": [0, 1, np.nan]})
    out = gate_balance(merge_indicators(df, table))
    assert np.isnan(out.loc[0, "u_wb_mean"]) and np.isnan(out.loc[0, "u_deficit_months"])
    assert out.loc[1, "u_wb_mean"] == 20.0 and out.loc[2, "u_deficit_months"] == 4.0
    assert list(out["u_ndvi"]) == [0.5, 0.6, 0.7]


def test_table_without_flag_is_untouched():
    df = pd.DataFrame({"unit_id": ["a"], "u_wb_mean": [1.0]})
    assert gate_balance(df).equals(df)
