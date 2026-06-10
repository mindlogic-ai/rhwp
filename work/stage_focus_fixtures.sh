#!/usr/bin/env bash
set -euo pipefail

stage() {
  local doc="$1"
  local src="$2"
  local ext="${src##*.}"
  mkdir -p "/tmp/diff/$doc"
  cp "$src" "/tmp/diff/$doc/source.$ext"
  printf '%s\t%s\n' "$doc" "/tmp/diff/$doc/source.$ext"
}

stage accountability_eval /Users/jaehoshin/Desktop/mindlogic/hwpx-lab/samples/accountability_eval.hwpx
stage report_form /Users/jaehoshin/Desktop/mindlogic/hwpx-lab/samples/report_form.hwpx
stage overseas_training /Users/jaehoshin/Desktop/mindlogic/hwpx-lab/samples/overseas_training.hwpx
stage meeting_summary /Users/jaehoshin/Desktop/mindlogic/hwpx-lab/samples/meeting_summary.hwpx
stage 15_3740450_research_admin_innovation_meeting_template /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwp-licensed/server/tests/hwp_validation/golden_tables/15_3740450_research_admin_innovation_meeting_template/_doc.hwpx
stage 20_3727659_resume_2605_ai /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwp-licensed/server/tests/hwp_validation/golden_tables/20_3727659_resume_2605_ai/_doc.hwpx
stage 05_3781559_medschool_car_2bu_je_plan /Users/jaehoshin/Desktop/mindlogic/factchat/worktree-hwp-licensed/server/tests/hwp_validation/golden_tables/05_3781559_medschool_car_2bu_je_plan/_doc.hwpx
