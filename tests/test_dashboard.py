"""Checks for national.dashboard that need no data: python -m tests.test_dashboard"""
import json
import tempfile
from pathlib import Path

from national import dashboard as D
from national import profile as P


def test_params_are_scored_indicators():
    """Every parameter of the dashboard is an indicator of the profile, so a weight set in the config reaches the page."""
    for pid, col, grp, label, unit, mult in D.PARAMS:
        assert col in P.DEFAULTS["indicators"], col
        assert grp in ("hist", "now", "canal")
    assert abs(sum(P.DEFAULTS["indicators"][c]["weight"] for _, c, g, *_ in D.PARAMS if g == "canal") - 1.0) < 1e-9   # the three canal weights split the old single weight


def test_assemble_fills_every_placeholder_and_keeps_script_tags_closed():
    data = {"meta": {}, "params": [], "khg": {"id": ["A"]}, "geo": []}
    prof = {"A": {"note": "</script><b>x</b>"}}                    # a payload that would end its tag early if not escaped
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "d.html"
        D.assemble(data, prof, out)
        h = out.read_text(encoding="utf-8")
    for ph in ("/*D3*/", "/*CSS*/", "/*JS*/", "/*DATA*/", "<!--PROFILES-->"):
        assert ph not in h, ph
    i = h.index('id="prof-A"')
    body = h[i:h.index("</script>", i)]
    assert json.loads(body[body.index(">") + 1:].replace("<\\/", "</"))["note"].startswith("</script>")
    assert h.count("<script") == h.count("</script>")             # every script tag is closed


if __name__ == "__main__":
    test_params_are_scored_indicators()
    test_assemble_fills_every_placeholder_and_keeps_script_tags_closed()
    print("ok")
