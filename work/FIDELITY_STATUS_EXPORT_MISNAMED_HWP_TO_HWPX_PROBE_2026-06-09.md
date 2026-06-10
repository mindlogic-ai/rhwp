# Export Roundtrip: Misnamed HWP to HWPX Probe

Status: probe / HWP-adapter-only

Representative: `45_form_grad_research_plan.hwpx`

Category: export roundtrip

## Classification

This representative is not a normal HWPX source roundtrip. The file name ends
in `.hwpx`, but the source bytes are binary HWP:

- `file .../samples/corpus/45_form_grad_research_plan.hwpx` reports
  `Hangul (Korean) Word Processor File 5.x`
- magic bytes are `d0 cf 11 e0 ...`
- `unzip` fails on the source
- loader reports `source_format: hwp`

The exported `.hwpx` is a real ZIP/HWPX package, so the failing path is
binary-HWP -> generated HWPX -> reload, not true HWPX -> HWPX preservation.

## Probe Result

Current mutated export probe:

- source load: 39 pages
- after mutation: 41 pages
- HWPX export in-memory outline: 41 pages
- generated HWPX reload: 55 pages
- HWP export/reload: 41 pages

The generated HWPX package contains three section XML files and many serialized
paragraph/table tags, but reload produces more pages and a reduced high-level
outline (`200` paragraphs, `30` tables). This points at HWP-to-HWPX serialization
or HWPX parser/serializer compatibility for binary-HWP-origin IR, not at the
accepted true-HWPX export path.

## Evidence

- Probe summary:
  `/tmp/hwp-export-roundtrip-probe-mutated-current-2026-06-09/summary.txt`
- Probe JSON:
  `/tmp/hwp-export-roundtrip-probe-mutated-current-2026-06-09/results.json`
- Source:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final/hwp-agent-spike/samples/corpus/45_form_grad_research_plan.hwpx`
- Generated HWPX:
  `/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwpx-final/hwp-agent-spike/exports/1780951945_9852cd5f_45_form_grad_research_plan.hwpx`

Commands run:

- `file <source> <generated-hwpx>`
- `xxd -l 16 <source>`
- `unzip -l <source>`
- `unzip -l <generated-hwpx>`
- `docker compose --env-file .env.docker run --rm -v ... dev /app/target/release/rhwp export-text <source>`
- `docker compose --env-file .env.docker run --rm -v ... dev /app/target/release/rhwp export-text <generated-hwpx>`

## Decision

Do not treat this as a blocker for accepted true-HWPX export/reload. Keep the
row as `probe-HWP-adapter`.

Future promotion needs a dedicated binary-HWP-origin HWPX export contract:

- select HWP-origin representatives explicitly by magic bytes, not extension;
- compare binary HWP export/reload separately from generated HWPX reload;
- add a focused structural regression only after locating whether the drift is
  caused by section serialization, table/control serialization, or parser reload
  interpretation of generated HWPX.
