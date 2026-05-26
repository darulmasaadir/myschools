"""Build Workflow + Workflow State + Workflow Action Master fixtures.

Source-of-truth for Phase 5 workflows. Run via:

    bench --site myschools.localhost execute myschools.scripts.build_workflows.main

Emits three JSON files under ``myschools/fixtures/`` that ``bench migrate``
imports. Mirrors the build_notifications.py pattern so the workflows are
generated, not hand-edited.

Two workflows shipped:

1. **MYS Inspection Finding Workflow**
   Draft -> Open (Submit) -> In Progress (Acknowledge) -> Resolved
   (Mark Resolved) -> Verified (Verify), with Audit Officer able to
   Reject Resolution (back to In Progress) or Cancel from Open.

2. **MYS Royalty Invoice Workflow**
   Draft -> Unpaid (Submit), with Cancel allowed from Unpaid / Partial /
   Overdue. The Unpaid <-> Partial <-> Paid <-> Overdue transitions are
   payment-driven and happen via ``db_set`` (bypasses workflow), which is
   the right behaviour for system-managed transitions.
"""

from __future__ import annotations

import json
import os

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(APP_ROOT, "fixtures")

ROLE_AUDIT = "Audit Officer"
ROLE_BR_DIRECTOR = "Branch Director"
ROLE_BR_PRINCIPAL = "Branch Principal"
ROLE_BR_ACCOUNTANT = "Branch Accountant"
ROLE_HO_DEPT_HEAD = "HO Dept Head"
ROLE_CEO = "Chief Executive"


ROLE_LOCKED = "System Manager"  # post-submit states: only admins can edit


def _state(state, doc_status, allow_edit=None):
	return {
		"doctype": "Workflow Document State",
		"state": state,
		"doc_status": str(doc_status),
		"update_field": "",
		"update_value": "",
		"allow_edit": allow_edit or ROLE_LOCKED,
		"is_optional_state": 0,
		"avoid_status_override": 0,
		"send_email": 0,
	}


def _transition(state, action, next_state, allowed):
	return {
		"doctype": "Workflow Transition",
		"state": state,
		"action": action,
		"next_state": next_state,
		"allowed": allowed,
		"allow_self_approval": 1,
	}


FINDING_STATES = [
	("Draft", 0, [ROLE_AUDIT, ROLE_BR_DIRECTOR, ROLE_BR_PRINCIPAL]),
	("Open", 1, []),
	("In Progress", 1, []),
	("Resolved", 1, []),
	("Verified", 1, []),
	("Cancelled", 2, []),
]

FINDING_TRANSITIONS = [
	("Draft", "Submit", "Open", [ROLE_AUDIT, ROLE_BR_DIRECTOR, ROLE_BR_PRINCIPAL]),
	("Open", "Acknowledge", "In Progress", [ROLE_BR_DIRECTOR, ROLE_BR_PRINCIPAL]),
	("In Progress", "Mark Resolved", "Resolved", [ROLE_BR_DIRECTOR, ROLE_BR_PRINCIPAL]),
	("Resolved", "Verify", "Verified", [ROLE_AUDIT]),
	("Resolved", "Reject Resolution", "In Progress", [ROLE_AUDIT]),
	("Open", "Cancel", "Cancelled", [ROLE_AUDIT]),
]

ROYALTY_STATES = [
	("Draft", 0, [ROLE_HO_DEPT_HEAD, ROLE_BR_ACCOUNTANT]),
	("Unpaid", 1, []),
	("Partial", 1, []),
	("Paid", 1, []),
	("Overdue", 1, []),
	("Cancelled", 2, []),
]

ROYALTY_TRANSITIONS = [
	("Draft", "Submit", "Unpaid", [ROLE_HO_DEPT_HEAD, ROLE_BR_ACCOUNTANT]),
	("Unpaid", "Cancel", "Cancelled", [ROLE_CEO, ROLE_HO_DEPT_HEAD]),
	("Partial", "Cancel", "Cancelled", [ROLE_CEO]),
	("Overdue", "Cancel", "Cancelled", [ROLE_CEO]),
]


def _expand_states(state_defs):
	rows = []
	for name, doc_status, editors in state_defs:
		if not editors:
			rows.append(_state(name, doc_status))
		else:
			for role in editors:
				rows.append(_state(name, doc_status, role))
	return rows


def _expand_transitions(transition_defs):
	rows = []
	for state, action, next_state, allowed_roles in transition_defs:
		for role in allowed_roles:
			rows.append(_transition(state, action, next_state, role))
	return rows


def _workflow(name, doctype, state_defs, transition_defs):
	return {
		"doctype": "Workflow",
		"name": name,
		"workflow_name": name,
		"document_type": doctype,
		"is_active": 1,
		"override_status": 0,
		"send_email_alert": 0,
		"workflow_state_field": "status",
		"states": _expand_states(state_defs),
		"transitions": _expand_transitions(transition_defs),
	}


WORKFLOWS = [
	_workflow(
		"MYS Inspection Finding Workflow",
		"MYS Inspection Finding",
		FINDING_STATES,
		FINDING_TRANSITIONS,
	),
	_workflow(
		"MYS Royalty Invoice Workflow",
		"MYS Royalty Invoice",
		ROYALTY_STATES,
		ROYALTY_TRANSITIONS,
	),
]

# Workflow State + Workflow Action Master rows that aren't pre-seeded in core.
# Core ships: Draft, Pending, Approved, Rejected, Submitted, Cancelled (states)
#             and Submit, Cancel, Approve, Reject, Review (actions).
# We need: Open, In Progress, Resolved, Verified, Unpaid, Partial, Paid, Overdue.
WORKFLOW_STATE_NAMES = [
	("Open", "warning"),
	("In Progress", "primary"),
	("Resolved", "info"),
	("Verified", "success"),
	("Unpaid", "warning"),
	("Partial", "primary"),
	("Paid", "success"),
	("Overdue", "danger"),
]

WORKFLOW_ACTION_NAMES = [
	"Acknowledge",
	"Mark Resolved",
	"Verify",
	"Reject Resolution",
]


def _state_master(name, style):
	return {
		"doctype": "Workflow State",
		"name": name,
		"workflow_state_name": name,
		"style": style,
	}


def _action_master(name):
	return {
		"doctype": "Workflow Action Master",
		"name": name,
		"workflow_action_name": name,
	}


def _write_json(filename, payload):
	path = os.path.join(FIXTURES_DIR, filename)
	with open(path, "w") as fh:
		json.dump(payload, fh, indent=1)
		fh.write("\n")
	return path


def main():
	os.makedirs(FIXTURES_DIR, exist_ok=True)
	state_path = _write_json(
		"workflow_state.json",
		[_state_master(name, style) for name, style in WORKFLOW_STATE_NAMES],
	)
	action_path = _write_json(
		"workflow_action_master.json",
		[_action_master(name) for name in WORKFLOW_ACTION_NAMES],
	)
	workflow_path = _write_json("workflow.json", WORKFLOWS)
	print(f"Wrote {state_path}")
	print(f"Wrote {action_path}")
	print(f"Wrote {workflow_path}")


if __name__ == "__main__":
	main()
