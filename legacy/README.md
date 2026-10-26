# Archive: the flat layout before packaging (2026-10-26)

`flat_layout_2026-10-26.zip` holds `common/`, `national/`, `subkhg/`, `investigations/` and `requirements.txt` as they were on 2026-10-26, before the code became the package `repeat_prioritisation` (`src/repeat_prioritisation/`, `pyproject.toml`). In that layout the programs ran from the repo root as `python -m subkhg.run`, `python -m national.profile` and so on, with `sys.path` inserts for the sibling folders.

The same folders were moved with `git mv` into `src/repeat_prioritisation/`, so their history continues there. The changes made in the move: imports are `repeat_prioritisation.<program>`; `sys.path` inserts removed; `national.run` and `subkhg.run` have a `main()`; the dashboard finds the hub through `REPEAT_HUB` or the workspace; command lines in docstrings name the console commands (`repeat-subkhg`, `repeat-national-profile`, ...). `requirements.txt` is replaced by the dependencies in `pyproject.toml`.

Nothing here is imported or run. Unzip it elsewhere to compare.
