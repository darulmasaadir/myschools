"""Build `myschools/fixtures/email_template.json` and
`myschools/fixtures/notification.json` from a single Python source.

Both fixtures share the same subject + body strings — Email Templates are the
reusable form (an HO admin can fire one manually from the desk),
Notifications are the automated form (fire on doc events / schedule).
Defining the strings once here means subject/body drift is impossible.

Regenerate via:
    python3 frappe-bench/apps/myschools/myschools/scripts/build_notifications.py
"""

from __future__ import annotations

import json
from pathlib import Path

MODULE = "MY School ERP"


# ---------------------------------------------------------------------------
# Source of truth — subject + body per notification
# ---------------------------------------------------------------------------

WRAPPER_OPEN = (
	'<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:14px;'
	'line-height:1.55;max-width:640px">'
	'<div style="background:#0F7A4A;color:#fff;padding:14px 18px;font-weight:700;'
	'font-size:15px;letter-spacing:0.3px">MY Schools</div>'
	'<div style="padding:18px;border:1px solid #E5E7EB;border-top:none">'
)
WRAPPER_CLOSE = (
	'<hr style="border:none;border-top:1px solid #E5E7EB;margin:20px 0 10px 0">'
	'<div style="font-size:11px;color:#6B7280">'
	"This is an automated message from MY Schools ERP. "
	"Replies are not monitored — log into the system to act on this notification."
	"</div></div></div>"
)


def wrap(html: str) -> str:
	return WRAPPER_OPEN + html + WRAPPER_CLOSE


# Each entry produces one Email Template + one Notification.
NOTIFICATIONS = [
	{
		"name": "MYS - Royalty Invoice Generated",
		"document_type": "MYS Royalty Invoice",
		"event": "Submit",
		"condition": "doc.docstatus == 1",
		"subject": "Royalty Invoice {{ doc.name }} generated — {{ doc.branch }}",
		"body": wrap(
			"<p>A new royalty invoice has been generated.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Invoice</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Period</td>"
			"<td>{{ doc.period_month }}/{{ doc.period_year }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Due Date</td>"
			"<td><strong>{{ frappe.utils.formatdate(doc.due_date, 'long') }}</strong></td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Total Royalty</td>"
			"<td><strong>{{ frappe.utils.fmt_money(doc.total_royalty, currency=doc.currency) }}</strong></td></tr>"
			"</table>"
			"<p>Open the invoice in the desk for the full campus-by-campus breakdown.</p>"
		),
		"recipients_roles": [
			"Chief Executive",
			"HO Dept Head",
			"Branch Director",
			"Branch Accountant",
		],
		"recipients_doc_fields": [],
		"attach_print": 1,
	},
	{
		"name": "MYS - Royalty Invoice Overdue",
		"document_type": "MYS Royalty Invoice",
		"event": "Days After",
		"date_changed": "due_date",
		"days_in_advance": 1,
		"condition": "doc.status in ('Unpaid', 'Partial', 'Overdue')",
		"subject": "OVERDUE: Royalty Invoice {{ doc.name }} — {{ doc.branch }}",
		"body": wrap(
			"<p style='color:#991B1B;font-weight:600'>"
			"This royalty invoice is past its due date and remains unpaid.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Invoice</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Due Date</td>"
			"<td>{{ frappe.utils.formatdate(doc.due_date, 'long') }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Outstanding</td>"
			"<td><strong style='color:#991B1B'>"
			"{{ frappe.utils.fmt_money(doc.outstanding_amount, currency=doc.currency) }}"
			"</strong></td></tr>"
			"</table>"
			"<p>Please reconcile payment or contact the franchisee.</p>"
		),
		"recipients_roles": [
			"Chief Executive",
			"HO Dept Head",
			"Branch Director",
			"Branch Accountant",
		],
		"recipients_doc_fields": [],
		"attach_print": 0,
	},
	{
		"name": "MYS - Inspection Finding Assigned",
		"document_type": "MYS Inspection Finding",
		"event": "Submit",
		"condition": "doc.docstatus == 1",
		"subject": "New finding {{ doc.name }} — {{ doc.severity }} at {{ doc.branch }}",
		"body": wrap(
			"<p>A new inspection finding has been recorded and requires action.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Finding</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Severity</td>"
			"<td><span style='display:inline-block;padding:2px 8px;border-radius:3px;"
			"font-weight:600;font-size:11px;background:"
			"{% if doc.severity == 'Critical' %}#FEE2E2;color:#991B1B"
			"{% elif doc.severity == 'Major' %}#FEF3C7;color:#92400E"
			"{% else %}#E5E7EB;color:#1F2937{% endif %}'>"
			"{{ doc.severity }}</span></td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Target Resolution</td>"
			"<td><strong>{{ frappe.utils.formatdate(doc.due_date, 'long') }}</strong></td></tr>"
			"</table>"
			"<p><strong>Title:</strong> {{ doc.title or '—' }}</p>"
			"<p style='font-size:13px;color:#6B7280'>{{ doc.description or '' }}</p>"
		),
		"recipients_roles": [
			"Branch Director",
			"Branch Principal",
			"Audit Officer",
		],
		"recipients_doc_fields": ["reported_by"],
		"attach_print": 0,
	},
	{
		"name": "MYS - Inspection Finding Overdue",
		"document_type": "MYS Inspection Finding",
		"event": "Days After",
		"date_changed": "due_date",
		"days_in_advance": 1,
		"condition": "doc.status in ('Open', 'In Progress')",
		"subject": "OVERDUE: Finding {{ doc.name }} — {{ doc.branch }}",
		"body": wrap(
			"<p style='color:#991B1B;font-weight:600'>"
			"This inspection finding has passed its target resolution date and is still open.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Finding</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Severity</td>"
			"<td>{{ doc.severity }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Status</td>"
			"<td>{{ doc.status }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Was due</td>"
			"<td><strong>{{ frappe.utils.formatdate(doc.due_date, 'long') }}</strong></td></tr>"
			"</table>"
			"<p>Open the finding in the desk and either close it or extend the target date.</p>"
		),
		"recipients_roles": [
			"Branch Director",
			"Branch Principal",
			"Audit Officer",
			"Academic Monitor",
		],
		"recipients_doc_fields": ["reported_by"],
		"attach_print": 0,
	},
	{
		"name": "MYS - Corrective Action Overdue",
		"document_type": "MYS Corrective Action",
		"event": "Days After",
		"date_changed": "due_date",
		"days_in_advance": 1,
		"condition": "doc.status in ('Planned', 'In Progress')",
		"subject": "OVERDUE: Corrective action for finding {{ doc.finding }}",
		"body": wrap(
			"<p style='color:#991B1B;font-weight:600'>"
			"A corrective action assigned to you is past its due date.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Action</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Finding</td>"
			"<td>{{ doc.finding }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Due</td>"
			"<td>{{ frappe.utils.formatdate(doc.due_date, 'long') }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Status</td>"
			"<td>{{ doc.status }}</td></tr>"
			"</table>"
			"<p><strong>What was planned:</strong> {{ doc.description or '—' }}</p>"
		),
		"recipients_roles": ["Branch Director", "Audit Officer"],
		"recipients_doc_fields": ["assigned_to"],
		"attach_print": 0,
	},
	{
		"name": "MYS - Franchise Agreement Expiring",
		"document_type": "MYS Franchise Agreement",
		"event": "Days Before",
		"date_changed": "end_date",
		"days_in_advance": 30,
		"condition": "doc.status == 'Active'",
		"subject": "Agreement {{ doc.name }} expires in 30 days — {{ doc.branch }}",
		"body": wrap(
			"<p>The franchise agreement below expires in 30 days. "
			"Initiate renewal or termination workflow.</p>"
			"<table style='border-collapse:collapse;font-size:13px;margin:10px 0 14px 0'>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Agreement</td>"
			"<td style='font-weight:600'>{{ doc.name }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Branch</td>"
			"<td>{{ doc.branch }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>Franchisee</td>"
			"<td>{{ doc.franchisee }}</td></tr>"
			"<tr><td style='padding:4px 12px 4px 0;color:#6B7280'>End Date</td>"
			"<td><strong>{{ frappe.utils.formatdate(doc.end_date, 'long') }}</strong></td></tr>"
			"</table>"
		),
		"recipients_roles": [
			"Chief Executive",
			"HO Dept Head",
			"Cluster Director",
			"Branch Director",
		],
		"recipients_doc_fields": [],
		"attach_print": 0,
	},
]


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

CREATION_TS = "2026-05-26 12:00:00.000000"


def build_email_templates() -> list[dict]:
	records = []
	for n in NOTIFICATIONS:
		records.append(
			{
				"name": n["name"],
				"creation": CREATION_TS,
				"docstatus": 0,
				"doctype": "Email Template",
				"modified": CREATION_TS,
				"modified_by": "Administrator",
				"owner": "Administrator",
				"subject": n["subject"],
				"use_html": 1,
				"response_html": n["body"],
				"response": "",
			}
		)
	return records


def build_notifications() -> list[dict]:
	records = []
	for n in NOTIFICATIONS:
		recipients = []
		for role in n.get("recipients_roles", []):
			recipients.append(
				{
					"doctype": "Notification Recipient",
					"receiver_by_role": role,
				}
			)
		for fieldname in n.get("recipients_doc_fields", []):
			recipients.append(
				{
					"doctype": "Notification Recipient",
					"receiver_by_document_field": fieldname,
				}
			)
		rec = {
			"name": n["name"],
			"creation": CREATION_TS,
			"docstatus": 0,
			"doctype": "Notification",
			"modified": CREATION_TS,
			"modified_by": "Administrator",
			"owner": "Administrator",
			"module": MODULE,
			"enabled": 1,
			"channel": "Email",
			"document_type": n["document_type"],
			"event": n["event"],
			"condition": n.get("condition", ""),
			"subject": n["subject"],
			"message_type": "HTML",
			"message": n["body"],
			"send_to_all_assignees": 0,
			"attach_print": n.get("attach_print", 0),
			"recipients": recipients,
		}
		if n["event"] in ("Days After", "Days Before"):
			rec["date_changed"] = n["date_changed"]
			rec["days_in_advance"] = n["days_in_advance"]
		records.append(rec)
	return records


def main():
	fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
	fixture_dir.mkdir(parents=True, exist_ok=True)

	emails = build_email_templates()
	(fixture_dir / "email_template.json").write_text(json.dumps(emails, indent=1, ensure_ascii=False) + "\n")
	print(f"Wrote email_template.json ({len(emails)} templates).")

	notifs = build_notifications()
	(fixture_dir / "notification.json").write_text(json.dumps(notifs, indent=1, ensure_ascii=False) + "\n")
	print(f"Wrote notification.json ({len(notifs)} notifications).")


if __name__ == "__main__":
	main()
