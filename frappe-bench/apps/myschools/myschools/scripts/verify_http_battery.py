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
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"
DEFAULT_HOST = "myschools.localhost"


ROLE_LANDING = [
	("ceo@mys.local", "mys-head-office"),
	("ho.head@mys.local", "mys-head-office"),
	("cluster.dir@mys.local", "mys-cluster"),
	("monitor@mys.local", "mys-inspection"),
	("audit@mys.local", "mys-inspection"),
	("campus@mys.local", "mys-campus"),
]


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
	for email, workspace in ROLE_LANDING:
		_check_role_landing(email, workspace, failures)
	for email in ["monitor@mys.local", "audit@mys.local"]:
		_check_inspection_user(email, failures)
	_check_teacher_user(failures)
	_check_admission_enquiry_public(failures)
	if failures:
		print("HTTP BATTERY FAILED:")
		for f in failures:
			print(f"  ✗ {f}")
		raise SystemExit(1)
	print(
		"HTTP BATTERY OK — Administrator + 4 branch + "
		f"{len(ROLE_LANDING)} desk roles + 2 inspection users + teacher portal + /admission-enquiry"
	)


def _check_teacher_user(failures: list[str]) -> None:
	"""Requires ``seed_portal_teacher`` or ``seed_e2e`` on the site (CI seeds both)."""
	email = "e2e_teacher@mys.local"
	op = _login(email, "mys-e2e-teacher")
	for path in [
		"/teacher",
		"/teacher/classes",
		"/teacher/schedule",
		"/teacher/attendance",
		"/teacher/assessments",
	]:
		status, body = _get(op, path)
		if status != 200:
			failures.append(f"{email} {path}: HTTP {status}")
		elif "You do not have access" in body:
			failures.append(f"{email} {path}: permission denied in body")
	status, body = _get(op, "/teacher/classes")
	if "E2E Teacher Class" not in body:
		failures.append(f"{email} /teacher/classes: expected seeded class row")
	# POST attendance — whitelist path only (Teacher cannot frappe.client.get_list).
	group_match = re.search(r"/teacher/class\?group=([^\"&]+)", body)
	if not group_match:
		failures.append(f"{email} /teacher/classes: no class roster link for attendance POST")
		return
	group = urllib.parse.unquote(group_match.group(1))
	from frappe.utils import nowdate

	att_date = nowdate()
	att_status, att_body = _get(
		op, f"/teacher/attendance?group={urllib.parse.quote(group)}&date={att_date}"
	)
	if att_status != 200:
		failures.append(f"{email} /teacher/attendance: HTTP {att_status}")
		return
	student_match = re.search(r'data-student="([^"]+)"', att_body)
	if not student_match:
		failures.append(f"{email} /teacher/attendance: no roster rows to mark")
		return
	student = student_match.group(1)
	att = _post_json(
		op,
		"/api/method/myschools.api.teacher_portal.save_class_attendance",
		{
			"student_group": group,
			"date": att_date,
			"rows": json.dumps([{"student": student, "status": "Present"}]),
		},
	)
	msg = att.get("message") or {}
	if not isinstance(msg, dict) or not msg.get("ok"):
		failures.append(f"{email} save_class_attendance: unexpected response {att}")
	plan_match = re.search(r"/teacher/assessment\?plan=([^\"&]+)", _get(op, "/teacher/assessments")[1])
	if plan_match:
		plan = urllib.parse.unquote(plan_match.group(1))
		score_body = _get(op, f"/teacher/assessment?plan={urllib.parse.quote(plan)}")[1]
		criteria_match = re.search(r'data-criteria="([^"]+)"', score_body)
		if criteria_match:
			scores = _post_json(
				op,
				"/api/method/myschools.api.teacher_portal.save_assessment_scores",
				{
					"assessment_plan": plan,
					"rows": json.dumps(
						[{"student": student, "scores": {criteria_match.group(1): 85}}]
					),
				},
			)
			score_msg = scores.get("message") or {}
			if not isinstance(score_msg, dict) or not score_msg.get("ok"):
				failures.append(f"{email} save_assessment_scores: unexpected response {scores}")


def _check_inspection_user(email: str, failures: list[str]) -> None:
	op = _login(email, "admin")
	for path in ["/inspection", "/inspection/visits", "/inspection/visits/new"]:
		status, body = _get(op, path)
		if status != 200:
			failures.append(f"{email} {path}: HTTP {status}")
		elif "You do not have access" in body:
			failures.append(f"{email} {path}: permission denied in body")
	# Exercise the whitelist that the portal's "Create draft visit" button calls.
	# A 400/500 here is the bug that GET-only HTTP smoke would miss.
	branch = _find_branch_for_inspector(op)
	if branch:
		resp = _post_json(
			op,
			"/api/method/myschools.api.inspection_portal.create_visit",
			{"branch": branch, "visit_type": "Routine"},
		)
		msg = resp.get("message") or {}
		if not isinstance(msg, dict) or not msg.get("name"):
			failures.append(f"{email} create_visit: unexpected response {resp}")


def _find_branch_for_inspector(opener) -> str | None:
	resp = _post_json(
		opener,
		"/api/method/frappe.client.get_list",
		{"doctype": "MYS Branch", "limit_page_length": 1, "fields": json.dumps(["name"])},
	)
	rows = resp.get("message") or []
	return rows[0].get("name") if rows else None


def _check_admission_enquiry_public(failures: list[str]) -> None:
	# 1. GET renders
	req = urllib.request.Request(f"{BASE}/admission-enquiry", headers={"Host": HOST})
	try:
		resp = urllib.request.urlopen(req, timeout=30)
		body = resp.read().decode("utf-8", errors="replace")
	except urllib.error.HTTPError as exc:
		failures.append(f"/admission-enquiry GET: HTTP {exc.code}")
		return
	if "Admission enquiry" not in body:
		failures.append("/admission-enquiry: missing page title marker")
		return
	# 2. POST as guest hits the whitelist and writes a Communication Log row.
	#    This catches the CSRF / route gap that HTTP-only smoke kept hiding.
	cj = http.cookiejar.CookieJar()
	guest_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
	# Frappe accepts guest POSTs to allow_guest whitelists without a CSRF
	# token if the request has no session — that mirrors the JS form using
	# window.csrf_token (which is null for guests). Verify the call succeeds.
	post = urllib.request.Request(
		f"{BASE}/api/method/myschools.api.inspection_portal.submit_admission_enquiry",
		data=urllib.parse.urlencode(
			{
				"parent_name": "HTTP Battery Parent",
				"phone": "03000000000",
				"message": "from verify_http_battery",
			}
		).encode(),
		headers={"Host": HOST},
		method="POST",
	)
	try:
		r = guest_opener.open(post, timeout=30)
		data = json.loads(r.read())
	except urllib.error.HTTPError as exc:
		failures.append(f"/admission-enquiry POST: HTTP {exc.code}")
		return
	msg = data.get("message") or {}
	if not isinstance(msg, dict) or not msg.get("name"):
		failures.append(f"/admission-enquiry POST: unexpected response {data}")


def _check_role_landing(email: str, workspace: str, failures: list[str]) -> None:
	"""For non-branch roles, prove the user can log in AND open their
	primary workspace via get_desktop_page without permission errors. The
	contents are role-shaped; we only assert no error envelope here."""
	try:
		op = _login(email, "admin")
	except urllib.error.HTTPError as exc:
		failures.append(f"{email}: login failed ({exc.code})")
		return
	page = _post_json(
		op,
		"/api/method/frappe.desk.desktop.get_desktop_page",
		{"page": json.dumps({"name": workspace})},
	)
	msg = page.get("message") or {}
	if not isinstance(msg, dict):
		failures.append(f"{email} {workspace}: unexpected response type {type(msg).__name__}")
		return
	if msg.get("error") or msg.get("exc_type"):
		failures.append(f"{email} {workspace}: {msg.get('error') or msg.get('exc_type')}")
		return
	if "shortcuts" not in msg and "number_cards" not in msg and "links" not in msg:
		failures.append(f"{email} {workspace}: empty desktop page payload")


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
