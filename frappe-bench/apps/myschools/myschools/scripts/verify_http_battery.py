"""HTTP PR-verification battery for branch desk + portal.

Run against the default site:
    cd frappe-bench && ./env/bin/python -c \\
        "from myschools.scripts.verify_http_battery import run; run()"

Run against a specific site (the Host header decides which Frappe site
serves the request — it must be a *.localhost alias of the target site
or the literal site name with `bench use` set):
    cd frappe-bench && ./env/bin/python -c \\
        "from myschools.scripts.verify_http_battery import run; run(host='test_fresh_install')"
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
DEFAULT_HOST = "myschools.localhost"


def run(host: str = DEFAULT_HOST):
	global HOST
	HOST = host
	failures: list[str] = []
	_check_admin_desk(failures)
	for email in [
		"branch.dir@mys.local",
		"principal@mys.local",
		"branch.admin@mys.local",
		"accountant@mys.local",
	]:
		_check_branch_user(email, failures)
	if failures:
		print("HTTP BATTERY FAILED:")
		for f in failures:
			print(f"  ✗ {f}")
		raise SystemExit(1)
	print("HTTP BATTERY OK — Administrator + 4 branch users")


def _login(email: str, password: str) -> urllib.request.OpenerDirector:
	cj = http.cookiejar.CookieJar()
	opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
	req = urllib.request.Request(
		f"{BASE}/api/method/login",
		data=urllib.parse.urlencode({"cmd": "login", "usr": email, "pwd": password}).encode(),
		headers={"Host": HOST},
		method="POST",
	)
	opener.open(req, timeout=30)
	return opener


def _post_json(opener, path: str, data: dict) -> dict:
	req = urllib.request.Request(
		f"{BASE}{path}",
		data=urllib.parse.urlencode(data).encode(),
		headers={"Host": HOST},
		method="POST",
	)
	return json.loads(opener.open(req, timeout=30).read())


def _get(opener, path: str) -> tuple[int, str]:
	req = urllib.request.Request(f"{BASE}{path}", headers={"Host": HOST})
	try:
		resp = opener.open(req, timeout=30)
		return resp.status, resp.read().decode("utf-8", errors="replace")
	except urllib.error.HTTPError as e:
		return e.code, e.read().decode("utf-8", errors="replace")


def _check_admin_desk(failures: list[str]) -> None:
	op = _login("Administrator", "admin")
	page = _post_json(
		op,
		"/api/method/frappe.desk.desktop.get_desktop_page",
		{"page": json.dumps({"name": "mys-branch"})},
	)
	msg = page.get("message") or {}
	nc = len((msg.get("number_cards") or {}).get("items") or [])
	if nc < 4:
		failures.append(f"Administrator mys-branch: expected 4 number_cards, got {nc}")


def _check_branch_user(email: str, failures: list[str]) -> None:
	op = _login(email, "admin")
	page = _post_json(
		op,
		"/api/method/frappe.desk.desktop.get_desktop_page",
		{"page": json.dumps({"name": "mys-branch"})},
	)
	msg = page.get("message") or {}
	labels = {x.get("label") for x in (msg.get("number_cards") or {}).get("items") or []}
	expected = {
		"Active Students",
		"This Month Royalty Invoiced",
		"This Month Fees Collected",
		"Overdue Findings",
	}
	missing = expected - labels
	if missing:
		failures.append(f"{email} desk missing cards: {sorted(missing)}")
	shortcuts = [x.get("label") for x in (msg.get("shortcuts") or {}).get("items") or []]
	if "Mobile Dashboard" not in shortcuts:
		failures.append(f"{email} desk missing Mobile Dashboard shortcut")
	for path in ["/branch", "/branch/findings", "/branch/royalty", "/branch/fees"]:
		status, body = _get(op, path)
		if status != 200:
			failures.append(f"{email} {path}: HTTP {status}")
		elif "You do not have access" in body:
			failures.append(f"{email} {path}: permission denied in body")
