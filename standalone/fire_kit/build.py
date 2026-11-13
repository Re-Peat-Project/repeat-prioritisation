"""Builds the standalone fire kit (zip) for KLH: the fire tally of the national dashboard as a folder that runs on its own.

    python repeat-prioritisation/standalone/fire_kit/build.py [--out DIR] [--registry CSV]

Copies template/ (README, config.yaml, requirements, pasang.bat, jalankan.bat, the command line in kebakaran_lahan/__main__.py),
the four modules the tally is made of (national/fire_common, fire_landstatus, fire_tables, fire_export, with their package
imports made relative) and the KHG registry, then zips it as DIR/kebakaran_lahan_<version>.zip (default DIR: the workspace's
_exports). The modules are not edited by hand in the kit: change them in the package and rebuild.
"""
import argparse
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parents[1] / "src" / "repeat_prioritisation" / "national"
MODULES = ["fire_common", "fire_landstatus", "fire_tables", "fire_export"]
NAME = "kebakaran_lahan"


def version():
    t = (HERE.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version\s*=\s*"([^"]+)"', t, re.M)[1]


def build(out, registry):
    d = out / f"{NAME}_{version()}"
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(HERE / "template", d, ignore=shutil.ignore_patterns("__pycache__"))
    (d / "data").mkdir()
    (d / "data" / "LETAKKAN_DATA_DI_SINI.txt").write_text("Salin file data masukan ke folder ini (lihat README.md, bagian Data).\n", encoding="utf-8")
    for m in MODULES:
        s = (PKG / f"{m}.py").read_text(encoding="utf-8")
        s = re.sub(r"from repeat_prioritisation\.national import (\w+) as (\w+)\n",
                   lambda x: f"from . import {x[1]} as {x[2]}\n" if x[1] in MODULES else x[0], s)
        s = s.replace("python -m repeat_prioritisation.national.fire_export", f"python -m {NAME}.fire_export")
        left = [ln.strip() for ln in s.splitlines() if "repeat_prioritisation" in ln and "import" in ln]
        # the only package imports left are inside main(), the dashboard's own entry points, which the kit does not call
        assert all("land as L" in ln for ln in left), (m, left)
        (d / NAME / f"{m}.py").write_text(s, encoding="utf-8")
    (d / NAME / "__init__.py").write_text(f'"""Burned area and hotspots by land status. Run: python -m {NAME} --config config.yaml"""\n__version__ = "{version()}"\n',
                                          encoding="utf-8")
    shutil.copy2(registry, d / "khg_registry.csv")
    z = shutil.make_archive(str(d), "zip", root_dir=d.parent, base_dir=d.name)
    print(d, "\n", z, f"{Path(z).stat().st_size / 1e3:.0f} kB")
    return d


def main():
    ws = HERE.parents[2]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ws / "_exports")
    ap.add_argument("--registry", type=Path, default=ws / "re-peat" / "sites" / "khg_registry.csv")
    a = ap.parse_args()
    build(a.out, a.registry)


if __name__ == "__main__":
    main()
