# Process: Print Formats

*Audience: anyone customising the look of a printed MY Schools document, or
debugging why a doc prints "blank" / falls back to a generic Frappe layout.*

The four branded PDF layouts that ship with MY School ERP — Royalty Invoice,
Inspection Report, Fee Receipt, Franchise Agreement — and how the renderer
finds them.

> **Fixtures**: [`myschools/fixtures/print_format.json`](../../frappe-bench/apps/myschools/myschools/fixtures/print_format.json) ·
> **Source of truth**: [`myschools/scripts/build_print_formats.py`](../../frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py) ·
> **Tests**: [`myschools/tests/test_print_formats.py`](../../frappe-bench/apps/myschools/myschools/tests/test_print_formats.py)

---

## 1. What ships

| Print Format            | Doctype                   | What it prints                                                  |
| ----------------------- | ------------------------- | --------------------------------------------------------------- |
| MYS Royalty Invoice     | `MYS Royalty Invoice`     | Header + campus breakdown table + totals + status badge         |
| MYS Inspection Report   | `MYS Inspection Visit`    | Scorecard tiles + severity-coloured checklist + recommendations |
| MYS Fee Receipt         | `Fees`                    | Student/program/term header + component table + PAID badge      |
| MYS Franchise Agreement | `MYS Franchise Agreement` | Royalty terms + financials + signature blocks                   |

All four use the MY Schools green (`#0F7A4A`) as the primary accent and inherit
the `MYS Default` Letter Head shipped by the navigation shell.

---

## 2. How they get picked

Two records work together to make "Print" on each doctype default to the MYS
layout:

1. **The `Print Format` record itself** — `custom_format=1` tells Frappe's
   `frappe.www.printview.get_rendered_template` to dispatch to the `html` field
   (our Jinja). Without that flag, Frappe falls back to the auto-built "Standard"
   layout and the `html` we shipped is silently ignored. (This is the #1 trap
   when authoring a new MYS Print Format — see the test
   `test_*_renders` for the regression guard.)

2. **A `Property Setter` per doctype** — `setup/install.py::set_default_print_formats`
   creates one Property Setter per target doctype setting
   `default_print_format = "MYS <whatever>"`. So when a user opens the print
   dialog on, say, a Fees record, the format picker defaults to "MYS Fee
   Receipt" instead of "Standard".

Both are exported via the `fixtures = [...]` block in `hooks.py` and re-applied
on every `after_migrate`, so a fresh install or a `bench migrate` puts the
system in the right shape with zero manual steps.

---

## 3. Editing a template

The templates live as triple-quoted strings inside
`myschools/scripts/build_print_formats.py`, **not** in the generated JSON.
Workflow:

```bash
# 1. Edit the Python source
$EDITOR frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py

# 2. Regenerate the fixture
python3 frappe-bench/apps/myschools/myschools/scripts/build_print_formats.py

# 3. Re-import
bench --site myschools.localhost migrate

# 4. Smoke-render (uses the first row of each target doctype on the site)
bench --site myschools.localhost execute \
    myschools.scripts.build_print_formats.smoke_render

# 5. Run the full test (asserts the marker text really lands in the HTML)
bench --site myschools.localhost run-tests --app myschools \
    --module myschools.tests.test_print_formats
```

If `smoke_render` reports `fail:marker-missing`, the most likely cause is
`custom_format` got dropped — Frappe rendered the doc with the Standard layout
and your Jinja never executed.

---

## 4. Why a Python source instead of editing the JSON directly

A Print Format's `html` is a multi-hundred-line Jinja template. Storing it
JSON-escaped — with every newline as `\n` and every quote as `\"` — makes it
unreviewable. Keeping the source in a Python file lets the templates stay as
plain triple-quoted strings, syntax-highlighted, and `git diff`-able. The
generated `print_format.json` is the artefact that ships; the script is what
produced it.

---

## 5. Why a Property Setter instead of editing the doctype JSON

Three of the four target doctypes (`Fees`, `Fee Structure`, `Student`) come
from `frappe/education`; one (`MYS Franchise Agreement`) is ours. We could
edit the MYS one's JSON directly, but doing so for the Education-owned ones is
out of bounds — we don't fork upstream apps. A Property Setter is the
Frappe-native, fixture-friendly way to set a DocType-level property without
touching the source JSON; it works the same for upstream and our own
doctypes, so we use the same mechanism for all four.

---

## 6. Adding a new format

1. Add a new `(NAME, DOCTYPE, JINJA)` tuple to the `FORMATS` list in
   `build_print_formats.py`.
2. If you want it to be the default for that doctype on `bench migrate`, add
   it to `DEFAULT_PRINT_FORMATS` in `setup/install.py`.
3. Add a test in `tests/test_print_formats.py` that asserts the record imports,
   the Property Setter wires it, and rendering against a real doc emits the
   expected marker text.
4. Regenerate + migrate + run tests (commands in §3).

That's it — no `hooks.py` edits needed; the existing `fixtures` filters
already export anything whose name starts with `MYS ` and any Property Setter
whose `doc_type` is one of the configured four. If your new format targets a
*new* doctype, extend the `doc_type` IN-clause in the Property Setter filter
in `hooks.py`.
