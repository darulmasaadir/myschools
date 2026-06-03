"""Enforce a ratcheting line-coverage floor after `bench run-tests --coverage`.

Reads ``coverage_floor.json`` in the app root and fails if total line
coverage for the ``myschools`` app (excluding ``tests/`` and ``scripts/``)
drops below the minimum. Bump the floor only when coverage improves in the
same PR.

``bench run-tests --coverage`` writes ``frappe-bench/sites/.coverage`` with
**absolute** file paths, so the include glob must match anywhere in the path.

Run from bench root (CI):
    ./env/bin/python apps/myschools/myschools/scripts/check_coverage_floor.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import coverage

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent.parent
FLOOR_FILE = APP_ROOT / "coverage_floor.json"

INCLUDE = ["*/myschools/myschools/*"]
OMIT = ["*/tests/*", "*/myschools/scripts/*"]


def _find_data_file() -> Path | None:
	for path in (
		Path.cwd() / ".coverage",
		Path.cwd() / "sites" / ".coverage",
		Path.cwd() / "apps" / "myschools" / ".coverage",
		APP_ROOT.parent.parent.parent / "sites" / ".coverage",
		APP_ROOT / ".coverage",
	):
		if path.is_file():
			return path
	return None


def main() -> int:
	if not FLOOR_FILE.is_file():
		print(f"Missing {FLOOR_FILE}", file=sys.stderr)
		return 1
	floor_pct = float(json.loads(FLOOR_FILE.read_text())["line_percent"])
	data_file = _find_data_file()
	if not data_file:
		print(
			"No .coverage data file found. Run bench run-tests --app myschools --coverage first.",
			file=sys.stderr,
		)
		return 1
	cov = coverage.Coverage(data_file=str(data_file))
	cov.load()
	# report() returns the total line-coverage percentage. Suppress its table
	# output (we only want the number) by sending it to a throwaway buffer.
	pct = cov.report(include=INCLUDE, omit=OMIT, skip_empty=True, file=io.StringIO())
	print(f"Line coverage: {pct:.1f}% (floor {floor_pct:.1f}%)")
	if pct + 1e-6 < floor_pct:
		print(
			f"FAIL: coverage {pct:.1f}% is below floor {floor_pct:.1f}%.",
			file=sys.stderr,
		)
		return 1
	print("Coverage floor OK.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
