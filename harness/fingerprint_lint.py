#!/usr/bin/env python3
"""Block content-string ('fingerprint') fixes in the rhwp engine.

The core anti-hardcode rule: a fix may branch on STRUCTURE (lineseg presence,
vpos resets, item type, table geometry) but NEVER on document CONTENT
(`text.contains("<hangul>")`, fixture-named fns). The corpus is train+test, so
content-keyed fixes memorize one doc's answer and generalize to nothing.

Scans the WORKING-TREE diff (unstaged + staged) of src/renderer and
src/document_core for ADDED lines that:
  - call .contains("...") / .starts_with("...") / == "..." with a literal
    containing non-ASCII (Hangul) or >=6 ASCII letters (doc-text-like), OR
  - define a fn whose name looks fixture-specific (is_sampleNN_, _hwp, doc id).
Existing debt is grandfathered via baseline.txt (exact added-line text).

Exit 1 (blocks commit) on any NEW offender. Exit 0 if clean.

Usage: fingerprint_lint.py [RHWP_DIR]
"""
import sys, os, re, subprocess

RHWP = sys.argv[1] if len(sys.argv) > 1 else \
    "/Users/jaehoshin/Desktop/mindlogic/factchat/worktree-rhwp-poc/rhwp"
BASELINE = os.path.join(os.path.dirname(__file__), "fingerprint_baseline.txt")
DIRS = ("src/renderer", "src/document_core")

CONTENT_CALL = re.compile(
    r'\.(?:contains|starts_with|ends_with|find)\("([^"]*)"\)|==\s*"([^"]+)"')
FIXTURE_FN = re.compile(
    r'\bfn\s+(is_sample\w+|\w*_hwp\b\w*|\w*fixture\w*|\w*_doc\d+\w*)\s*\(')
HANGUL = re.compile(r'[가-힣]')


def looks_like_doctext(s):
    if HANGUL.search(s):
        return True
    return len(re.findall(r'[A-Za-z]', s)) >= 6


def added_lines():
    """Return added (+) lines from working-tree diff against HEAD for DIRS."""
    cmd = ["git", "-C", RHWP, "diff", "HEAD", "--unified=0", "--"] + list(DIRS)
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    for ln in out.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            yield ln[1:]


def main():
    baseline = set()
    if os.path.exists(BASELINE):
        baseline = {l.rstrip("\n") for l in open(BASELINE, encoding="utf-8")}
    offenders = []
    for raw in added_lines():
        line = raw.strip()
        if not line or line.startswith("//") or line in baseline:
            continue
        hit = None
        m = CONTENT_CALL.search(line)
        if m:
            lit = m.group(1) or m.group(2) or ""
            if looks_like_doctext(lit):
                hit = f'content-string match: "{lit[:40]}"'
        if not hit and FIXTURE_FN.search(line):
            hit = f'fixture-named fn: {FIXTURE_FN.search(line).group(1)}'
        if hit:
            offenders.append((hit, line[:100]))
    if offenders:
        print("FINGERPRINT LINT FAILED — content-keyed fix detected:")
        for why, ln in offenders:
            print(f"  [{why}]  {ln}")
        print("\nFix must key on STRUCTURE, not document content. "
              "If this is intentional grandfathered debt, add the exact added "
              "line to harness/fingerprint_baseline.txt.")
        sys.exit(1)
    print("fingerprint_lint: clean (0 new content-keyed fixes)")


if __name__ == "__main__":
    main()
