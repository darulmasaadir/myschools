import frappe

def main():
    for wf_name in ("MYS Inspection Finding Workflow", "MYS Royalty Invoice Workflow"):
        wf = frappe.get_doc("Workflow", wf_name)
        print(f"\n=== {wf_name} ===")
        print(f"  document_type: {wf.document_type}, is_active: {wf.is_active}, field: {wf.workflow_state_field}")
        print(f"  States: {len(wf.states)} rows")
        for s in wf.states:
            print(f"    {s.state} (docstatus={s.doc_status}) editable_by={s.allow_edit}")
        print(f"  Transitions: {len(wf.transitions)} rows")
        for t in wf.transitions:
            print(f"    {t.state} --[{t.action}]--> {t.next_state} by {t.allowed}")
