# Focus Validation Playbook

This is the user-selected problem set from the June 1 visual review. It is a
working queue, not a replacement for the full corpus gate.

## Open

- `http://127.0.0.1:8799/_FOCUS_INDEX.html`
- Each row links to the existing Hancom-left / rhwp-right comparison folder.

## First Pass

Start with `quick`:

```bash
cd /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp
python3 harness/focus_next.py
python3 harness/focus_index.py
bash harness/focus_gate.sh quick
```

Skip `giant` until shorter docs stop yielding general fixes. The obvious first
cluster is spacing/table height:

1. `report_form` and `meeting_summary` for short line-height drift in opposite directions.
2. `accountability_eval` for severe table row-height under-measure.
3. `form_01`, `form_04`, `form_15`, `tiny_03` for short wild-form visual checks.
4. `15_3740450_research_admin_innovation_meeting_template` and `meeting` for image/table pagination.

## Commit Rule

`focus_gate.sh` is only a cheap loop. Before committing any renderer change:

```bash
python3 harness/fingerprint_lint.py
bash harness/gate.sh
```

Then re-render the touched target's `rhwp_svg_cur/`, open the comparison, and
commit only if the visual result moves toward Hancom without growing the overfit
baseline.
