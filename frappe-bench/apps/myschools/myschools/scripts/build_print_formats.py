"""Build `myschools/fixtures/print_format.json` from inline Jinja templates.

We keep the templates in this Python file so each one is readable as a
plain triple-quoted string instead of a one-line JSON with escaped
quotes and newlines. The generated JSON file is what ships and gets
imported on `bench migrate`; this script is the source of truth that
produced it.

Regenerate via:
  python3 frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py
"""

from __future__ import annotations

import json
from pathlib import Path

MODULE = "MY School ERP"

# ---------------------------------------------------------------------------
# Jinja templates
# ---------------------------------------------------------------------------

ROYALTY_INVOICE = r"""
{%- if letter_head and not no_letterhead %}
<div class="letter-head" style="margin-bottom:14px">{{ letter_head|safe }}</div>
{% endif -%}
<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <div>
      <div style="font-size:22px;font-weight:800;letter-spacing:0.5px;color:#0F7A4A">ROYALTY INVOICE</div>
      <div style="font-size:11px;color:#6B7280">{{ doc.name }}</div>
    </div>
    <div style="text-align:right">
      <span style="display:inline-block;padding:4px 10px;border-radius:4px;font-weight:600;font-size:11px;
        {%- if doc.status == 'Paid' %} background:#D1FAE5;color:#065F46 {%- elif doc.status == 'Overdue' %} background:#FEE2E2;color:#991B1B
        {%- elif doc.status == 'Partial' %} background:#FEF3C7;color:#92400E {%- else %} background:#E5E7EB;color:#1F2937 {%- endif -%}">
        {{ doc.status }}
      </span>
    </div>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Invoice Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.formatdate(doc.invoice_date, "long") if doc.invoice_date else "" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Due Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.formatdate(doc.due_date, "long") if doc.due_date else "" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Branch</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.branch }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Cluster</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.cluster or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Period</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.period_month }}/{{ doc.period_year }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Franchisee</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.franchisee or "—" }}</td>
    </tr>
  </table>

  <div style="font-weight:700;color:#0F7A4A;margin:14px 0 6px 0;font-size:13px">Campus Breakdown</div>
  <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead>
      <tr style="background:#0F7A4A;color:#fff">
        <th style="padding:8px 10px;text-align:left">Campus</th>
        <th style="padding:8px 10px;text-align:left">Type</th>
        <th style="padding:8px 10px;text-align:right">Collection</th>
        <th style="padding:8px 10px;text-align:right">Rate</th>
        <th style="padding:8px 10px;text-align:right">Royalty</th>
      </tr>
    </thead>
    <tbody>
      {% for line in doc.campus_lines %}
      <tr>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB">{{ line.campus }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;color:#6B7280">{{ line.campus_type or "—" }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:right">{{ frappe.utils.fmt_money(line.collection_amount, currency=doc.currency) }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:right">{{ "%.2f"|format(line.rate_percent or 0) }}%</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:right;font-weight:600">{{ frappe.utils.fmt_money(line.royalty_amount, currency=doc.currency) }}</td>
      </tr>
      {% else %}
      <tr><td colspan="5" style="padding:10px;text-align:center;color:#6B7280">No campus lines</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <table style="width:50%;margin-left:auto;margin-top:14px;border-collapse:collapse;font-size:12px">
    <tr>
      <td style="padding:6px 10px;color:#6B7280">Total Collection</td>
      <td style="padding:6px 10px;text-align:right">{{ frappe.utils.fmt_money(doc.total_collection, currency=doc.currency) }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;color:#6B7280">Effective Rate</td>
      <td style="padding:6px 10px;text-align:right">{{ "%.2f"|format(doc.applicable_rate or 0) }}%</td>
    </tr>
    <tr style="background:#F0FDF4">
      <td style="padding:8px 10px;font-weight:700;color:#0F7A4A">Royalty Amount</td>
      <td style="padding:8px 10px;text-align:right;font-weight:700;color:#0F7A4A">{{ frappe.utils.fmt_money(doc.royalty_amount, currency=doc.currency) }}</td>
    </tr>
    {% if doc.paid_amount %}
    <tr>
      <td style="padding:6px 10px;color:#6B7280">Paid</td>
      <td style="padding:6px 10px;text-align:right">{{ frappe.utils.fmt_money(doc.paid_amount, currency=doc.currency) }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;color:#6B7280">Outstanding</td>
      <td style="padding:6px 10px;text-align:right">{{ frappe.utils.fmt_money(doc.outstanding_amount, currency=doc.currency) }}</td>
    </tr>
    {% endif %}
  </table>

  {% if doc.notes %}
  <div style="margin-top:14px;padding:10px;background:#F9FAFB;border-left:3px solid #0F7A4A">
    <div style="font-weight:600;color:#6B7280;font-size:11px;margin-bottom:4px">Notes</div>
    <div style="white-space:pre-wrap">{{ doc.notes }}</div>
  </div>
  {% endif %}
</div>
"""

INSPECTION_REPORT = r"""
{%- if letter_head and not no_letterhead %}
<div class="letter-head" style="margin-bottom:14px">{{ letter_head|safe }}</div>
{% endif -%}
<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:12px">
  <div style="margin-bottom:14px">
    <div style="font-size:22px;font-weight:800;letter-spacing:0.5px;color:#0F7A4A">INSPECTION REPORT</div>
    <div style="font-size:11px;color:#6B7280">{{ doc.name }} &mdash; {{ doc.visit_type }}</div>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Visit Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.formatdate(doc.visit_date, "long") if doc.visit_date else "" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Inspector</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.inspector or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Branch</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.branch }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Campus</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.campus or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Template</td>
      <td colspan="3" style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.checklist_template or "—" }}</td>
    </tr>
  </table>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px;background:#F0FDF4">
    <tr>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">Items</div>
        <div style="font-size:18px;font-weight:700">{{ doc.total_items or 0 }}</div>
      </td>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">Passed</div>
        <div style="font-size:18px;font-weight:700;color:#065F46">{{ doc.items_passed or 0 }}</div>
      </td>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">Failed</div>
        <div style="font-size:18px;font-weight:700;color:#991B1B">{{ doc.items_failed or 0 }}</div>
      </td>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">N/A</div>
        <div style="font-size:18px;font-weight:700;color:#6B7280">{{ doc.items_na or 0 }}</div>
      </td>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">Score</div>
        <div style="font-size:18px;font-weight:700;color:#0F7A4A">{{ "%.1f"|format(doc.score_percent or 0) }}%</div>
      </td>
      <td style="padding:10px;text-align:center;border:1px solid #BBF7D0">
        <div style="font-size:11px;color:#6B7280">Weighted</div>
        <div style="font-size:18px;font-weight:700;color:#0F7A4A">{{ "%.1f"|format(doc.weighted_score or 0) }}%</div>
      </td>
    </tr>
  </table>

  {% if doc.areas_inspected %}
  <div style="margin-bottom:10px">
    <div style="font-weight:700;color:#0F7A4A;font-size:13px;margin-bottom:4px">Areas Inspected</div>
    <div style="white-space:pre-wrap">{{ doc.areas_inspected }}</div>
  </div>
  {% endif %}

  <div style="font-weight:700;color:#0F7A4A;margin:14px 0 6px 0;font-size:13px">Checklist Results</div>
  <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead>
      <tr style="background:#0F7A4A;color:#fff">
        <th style="padding:8px 10px;text-align:left">Item</th>
        <th style="padding:8px 10px;text-align:left">Category</th>
        <th style="padding:8px 10px;text-align:left">Severity</th>
        <th style="padding:8px 10px;text-align:center">Result</th>
        <th style="padding:8px 10px;text-align:right">Score</th>
      </tr>
    </thead>
    <tbody>
      {% for line in doc.checklist_results %}
      <tr>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB">{{ line.item_text }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;color:#6B7280">{{ line.category or "—" }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB">
          <span style="padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600;
            {%- if line.severity == 'Critical' %} background:#FEE2E2;color:#991B1B
            {%- elif line.severity == 'Major' %} background:#FEF3C7;color:#92400E
            {%- else %} background:#E5E7EB;color:#374151 {%- endif -%}">{{ line.severity }}</span>
        </td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:center;font-weight:600;
          {%- if line.result == 'Pass' %} color:#065F46
          {%- elif line.result == 'Fail' %} color:#991B1B
          {%- else %} color:#6B7280 {%- endif -%}">{{ line.result or "—" }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:right">{{ line.score }}/{{ line.max_score }}</td>
      </tr>
      {% else %}
      <tr><td colspan="5" style="padding:10px;text-align:center;color:#6B7280">No results recorded</td></tr>
      {% endfor %}
    </tbody>
  </table>

  {% if doc.summary %}
  <div style="margin-top:14px">
    <div style="font-weight:700;color:#0F7A4A;font-size:13px;margin-bottom:4px">Summary</div>
    <div>{{ doc.summary }}</div>
  </div>
  {% endif %}

  {% if doc.recommendations %}
  <div style="margin-top:10px;padding:10px;background:#F0FDF4;border-left:3px solid #0F7A4A">
    <div style="font-weight:700;color:#0F7A4A;font-size:12px;margin-bottom:4px">Recommendations</div>
    <div>{{ doc.recommendations }}</div>
  </div>
  {% endif %}
</div>
"""

FEE_RECEIPT = r"""
{%- if letter_head and not no_letterhead %}
<div class="letter-head" style="margin-bottom:14px">{{ letter_head|safe }}</div>
{% endif -%}
<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
    <div>
      <div style="font-size:22px;font-weight:800;letter-spacing:0.5px;color:#0F7A4A">FEE RECEIPT</div>
      <div style="font-size:11px;color:#6B7280">{{ doc.name }}</div>
    </div>
    <div style="text-align:right">
      <span style="display:inline-block;padding:4px 10px;border-radius:4px;font-weight:600;font-size:11px;
        {%- if (doc.outstanding_amount or 0) == 0 %} background:#D1FAE5;color:#065F46
        {%- else %} background:#FEF3C7;color:#92400E {%- endif -%}">
        {{ "PAID" if (doc.outstanding_amount or 0) == 0 else "OUTSTANDING" }}
      </span>
    </div>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.formatdate(doc.posting_date, "long") if doc.posting_date else "" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Due Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.formatdate(doc.due_date, "long") if doc.due_date else "" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Student</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.student_name or doc.student }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Program</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.program or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Academic Year</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.academic_year or "—" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Term</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.academic_term or "—" }}</td>
    </tr>
  </table>

  <div style="font-weight:700;color:#0F7A4A;margin:14px 0 6px 0;font-size:13px">Fee Components</div>
  <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead>
      <tr style="background:#0F7A4A;color:#fff">
        <th style="padding:8px 10px;text-align:left">Fee Category</th>
        <th style="padding:8px 10px;text-align:left">Description</th>
        <th style="padding:8px 10px;text-align:right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for c in doc.components %}
      <tr>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB">{{ c.fees_category }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;color:#6B7280">{{ c.description or "—" }}</td>
        <td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;text-align:right">{{ frappe.utils.fmt_money(c.amount, currency=doc.currency) }}</td>
      </tr>
      {% else %}
      <tr><td colspan="3" style="padding:10px;text-align:center;color:#6B7280">No components</td></tr>
      {% endfor %}
    </tbody>
  </table>

  <table style="width:50%;margin-left:auto;margin-top:14px;border-collapse:collapse;font-size:12px">
    <tr style="background:#F0FDF4">
      <td style="padding:8px 10px;font-weight:700;color:#0F7A4A">Grand Total</td>
      <td style="padding:8px 10px;text-align:right;font-weight:700;color:#0F7A4A">{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</td>
    </tr>
    {% if doc.outstanding_amount and doc.outstanding_amount > 0 %}
    <tr>
      <td style="padding:6px 10px;color:#6B7280">Outstanding</td>
      <td style="padding:6px 10px;text-align:right">{{ frappe.utils.fmt_money(doc.outstanding_amount, currency=doc.currency) }}</td>
    </tr>
    {% endif %}
  </table>

  {% if doc.grand_total_in_words %}
  <div style="margin-top:10px;font-style:italic;color:#6B7280;font-size:11px">
    In Words: {{ doc.grand_total_in_words }}
  </div>
  {% endif %}
</div>
"""


LEAVING_CERTIFICATE = r"""
{%- if letter_head and not no_letterhead %}
<div class="letter-head" style="margin-bottom:14px">{{ letter_head|safe }}</div>
{% endif -%}
<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:12px">
  <div style="text-align:center;margin-bottom:18px">
    <div style="font-size:22px;font-weight:800;letter-spacing:1px;color:#0F7A4A">SCHOOL LEAVING CERTIFICATE</div>
    <div style="font-size:11px;color:#6B7280">Certificate No. {{ doc.certificate_number }}</div>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Student</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.student_name or doc.student }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">MYS Student ID</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.mys_student_id or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Branch</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.branch }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Campus</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.campus or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Date of Leaving</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ frappe.utils.formatdate(doc.leaving_date, "long") if doc.leaving_date else "" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Record</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.name }}</td>
    </tr>
  </table>

  <div style="margin:14px 0;line-height:1.7;text-align:justify">
    This is to certify that <strong>{{ doc.student_name or doc.student }}</strong>
    {%- if doc.mys_student_id %} (ID: {{ doc.mys_student_id }}){% endif %}
    was a student at <strong>{{ doc.branch }}</strong>
    {%- if doc.campus %} — {{ doc.campus }} campus{% endif %}
    and left the school on <strong>{{ frappe.utils.formatdate(doc.leaving_date, "long") if doc.leaving_date else "—" }}</strong>.
  </div>

  {% if doc.reason_for_leaving %}
  <div style="margin-top:10px">
    <div style="font-weight:700;color:#0F7A4A;font-size:13px;margin-bottom:4px">Reason for Leaving</div>
    <div style="text-align:justify;line-height:1.6">{{ doc.reason_for_leaving }}</div>
  </div>
  {% endif %}

  <div style="margin-top:36px;display:flex;justify-content:space-between">
    <div style="width:45%;border-top:1px solid #1A1A1A;padding-top:6px;text-align:center;font-size:11px;color:#6B7280">
      Branch Principal
    </div>
    <div style="width:45%;border-top:1px solid #1A1A1A;padding-top:6px;text-align:center;font-size:11px;color:#6B7280">
      Branch Director
    </div>
  </div>
</div>
"""

FRANCHISE_AGREEMENT = r"""
{%- if letter_head and not no_letterhead %}
<div class="letter-head" style="margin-bottom:14px">{{ letter_head|safe }}</div>
{% endif -%}
<div style="font-family:Inter,Arial,sans-serif;color:#1A1A1A;font-size:12px">
  <div style="text-align:center;margin-bottom:18px">
    <div style="font-size:22px;font-weight:800;letter-spacing:1px;color:#0F7A4A">FRANCHISE AGREEMENT</div>
    <div style="font-size:11px;color:#6B7280">{{ doc.name }}</div>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Status</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.status }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Branch</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.branch }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Franchisee</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.franchisee }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Company</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.company or "—" }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Start Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ frappe.utils.formatdate(doc.start_date, "long") if doc.start_date else "" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">End Date</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ frappe.utils.formatdate(doc.end_date, "long") if doc.end_date else "Open" }}</td>
    </tr>
  </table>

  <div style="font-weight:700;color:#0F7A4A;margin:14px 0 6px 0;font-size:13px">Royalty Terms</div>
  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Default Rate</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ "%.2f"|format(doc.default_royalty_rate or 0) }}%</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Base</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ doc.royalty_base }}</td>
    </tr>
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Billing Day</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.billing_day or "—" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;font-weight:600;color:#6B7280">Grace Days</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB">{{ doc.grace_days or 0 }}</td>
    </tr>
  </table>

  <div style="font-weight:700;color:#0F7A4A;margin:14px 0 6px 0;font-size:13px">Financials</div>
  <table style="width:100%;border-collapse:collapse;margin-bottom:14px">
    <tr>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Franchise Fee</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">{{ frappe.utils.fmt_money(doc.franchise_fee, currency=doc.currency) if doc.franchise_fee else "—" }}</td>
      <td style="padding:6px 10px;background:#F9FAFB;border:1px solid #E5E7EB;width:25%;font-weight:600;color:#6B7280">Security Deposit</td>
      <td style="padding:6px 10px;border:1px solid #E5E7EB;width:25%">
        {{ frappe.utils.fmt_money(doc.security_deposit, currency=doc.currency) if doc.security_deposit else "—" }}
        {% if doc.deposit_received %}<span style="color:#065F46;font-size:10px"> (received)</span>{% endif %}
      </td>
    </tr>
  </table>

  {% if doc.agreement_terms %}
  <div style="margin-top:14px">
    <div style="font-weight:700;color:#0F7A4A;font-size:13px;margin-bottom:6px">Agreement Terms</div>
    <div style="text-align:justify;line-height:1.6">{{ doc.agreement_terms }}</div>
  </div>
  {% endif %}

  <div style="margin-top:36px;display:flex;justify-content:space-between">
    <div style="width:45%;border-top:1px solid #1A1A1A;padding-top:6px;text-align:center;font-size:11px;color:#6B7280">
      Franchisee Signature
    </div>
    <div style="width:45%;border-top:1px solid #1A1A1A;padding-top:6px;text-align:center;font-size:11px;color:#6B7280">
      MY Schools Authorised Signatory
    </div>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

FORMATS = [
	("MYS Royalty Invoice", "MYS Royalty Invoice", ROYALTY_INVOICE),
	("MYS Inspection Report", "MYS Inspection Visit", INSPECTION_REPORT),
	("MYS Fee Receipt", "Fees", FEE_RECEIPT),
	("MYS Leaving Certificate", "MYS Student Leaving", LEAVING_CERTIFICATE),
	("MYS Franchise Agreement", "MYS Franchise Agreement", FRANCHISE_AGREEMENT),
]


def _record(name: str, doc_type: str, html: str) -> dict:
	return {
		"absolute_value": 0,
		"align_labels_right": 0,
		# custom_format=1 routes the renderer through our Jinja `html` field.
		# Without it, Frappe falls back to the auto-built "Standard" layout
		# and ignores `html` entirely.
		"custom_format": 1,
		"default_print_language": "en",
		"disabled": 0,
		"doc_type": doc_type,
		"doctype": "Print Format",
		"font": "Default",
		"font_size": 14,
		"html": html.strip(),
		"line_breaks": 0,
		"margin_bottom": 15.0,
		"margin_left": 15.0,
		"margin_right": 15.0,
		"margin_top": 15.0,
		"module": MODULE,
		"name": name,
		"page_number": "Hide",
		"print_format_builder": 0,
		"print_format_type": "Jinja",
		"raw_printing": 0,
		"show_section_headings": 0,
		"standard": "No",
	}


def build() -> list[dict]:
	return [_record(n, dt, html) for n, dt, html in FORMATS]


def main():
	fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
	fixture_dir.mkdir(parents=True, exist_ok=True)
	out = fixture_dir / "print_format.json"
	records = build()
	out.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n")
	print(f"Wrote {out} ({len(records)} print formats).")


def smoke_render():
	"""Bench-executable smoke test: pick one row of each target doctype,
	render it through the MYS print format, and assert the template doesn't
	raise. Returns a per-format pass/fail dict.

	Run via:
	  bench --site <site> execute myschools.scripts.build_print_formats.smoke_render
	"""
	import frappe
	from frappe.www.printview import get_html_and_style

	# Each case: doctype, print_format, marker string that ONLY the MYS Jinja
	# template emits (uppercased heading) — so the smoke catches a fallback
	# to Frappe's auto-built Standard layout, not just a missing record.
	cases = [
		("MYS Royalty Invoice", "MYS Royalty Invoice", "ROYALTY INVOICE"),
		("MYS Inspection Visit", "MYS Inspection Report", "INSPECTION REPORT"),
		("MYS Franchise Agreement", "MYS Franchise Agreement", "FRANCHISE AGREEMENT"),
		("Fees", "MYS Fee Receipt", "FEE RECEIPT"),
	]
	results = {}
	for doctype, pf, marker in cases:
		name = frappe.db.get_value(doctype, {}, "name")
		if not name:
			results[pf] = "skip:no-data"
			continue
		try:
			out = get_html_and_style(
				doc=doctype,
				name=name,
				print_format=pf,
				no_letterhead=0,
			)
			html = (out or {}).get("html") or ""
			results[pf] = f"ok:{len(html)}b" if marker in html else "fail:marker-missing"
		except Exception as e:
			results[pf] = f"error:{type(e).__name__}:{e}"
	return results


if __name__ == "__main__":
	main()
