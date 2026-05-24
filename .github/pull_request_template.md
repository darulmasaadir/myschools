<!--
Thanks for the contribution. Please fill out every section.
PRs missing context will be sent back without review.
-->

## Summary

<!-- One or two sentences: what does this PR do and why? -->

## Type

- [ ] feat — new functionality
- [ ] fix — bug fix
- [ ] refactor — no behaviour change
- [ ] perf — performance improvement
- [ ] docs — documentation only
- [ ] test — adding or fixing tests
- [ ] build / ci / chore — tooling, dependencies, infra

## DocType / migration impact

- [ ] No DocType changes
- [ ] Added new DocType(s): <list>
- [ ] Modified existing DocType field(s): <list — and note if a rename / backfill is needed>
- [ ] Added a patch in `myschools/patches/` and listed it in `patches.txt`
- [ ] Fixtures re-exported (`bench export-fixtures --app myschools`)

## Permissions / security

- [ ] No permission rules changed
- [ ] Updated `permission_query_conditions` — confirmed isolation still works for Branch / Cluster / HO scopes
- [ ] Added/changed a role — listed it in `FRANCHISE_ROLES` in `setup/install.py`

## Royalty / financial impact

- [ ] Not financial
- [ ] Touches royalty calculation — included a unit test asserting the new behaviour
- [ ] Touches Company / Cost Center linkage — confirmed multi-Company books still balance

## Verification

<!-- What did you actually run? Paste relevant output. -->

```
bench --site myschools.localhost migrate
bench --site myschools.localhost run-tests --app myschools
pre-commit run --all-files
```

## Screenshots / videos

<!-- Required for any UI change. -->

## Related issues

Closes #
