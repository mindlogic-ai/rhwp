#!/usr/bin/env python3
"""Fail new renderer fidelity fixes that key off fixture text.

The renderer may inspect HWP/HWPX structure: line segments, controls, table
geometry, wrap modes, styles, numbering metadata, and positions. It must not
recognize a real document by body text and branch to a bespoke answer.

This check intentionally uses a baseline. Existing debt stays visible, but new
content fingerprints or fixture-named helpers fail CI until they are rewritten
as structural engine rules or the legacy debt is intentionally removed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "scripts" / "renderer_overfit_baseline.txt"
SCAN_PATHS = (
    REPO_ROOT / "src" / "renderer",
    REPO_ROOT / "src" / "document_core" / "queries" / "rendering.rs",
    REPO_ROOT / "src" / "wasm_api.rs",
)

TEXT_PROBE_RE = re.compile(
    r"""
    (?P<receiver>[A-Za-z_][A-Za-z0-9_]*\.)?text
    \s*\.\s*
    (?P<method>contains|starts_with|ends_with)
    \s*\(\s*
    "(?P<literal>(?:\\.|[^"\\])*)"
    """,
    re.VERBOSE | re.DOTALL,
)

IDENT_RE = re.compile(r"\b(?:fn|let|const|static)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)")
FIXTURE_IDENTIFIER_RE = re.compile(
    r"(?:^|_)(?:fixture|sample\d+|oracle|golden|tsinghua|capsule|coffee|kstar|"
    r"student|exchange|natural_sci|medschool|mou|snu)(?:_|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    path: str
    subject: str
    line: int
    detail: str

    @property
    def key(self) -> str:
        return f"{self.rule}|{self.path}|{self.subject}"


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for path in SCAN_PATHS:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.rs")))
    return sorted(set(files))


def looks_like_document_text(literal: str) -> bool:
    decoded = bytes(literal, "utf-8").decode("unicode_escape", errors="ignore")
    if decoded in {"\\t", "\\n", "\\r", "\\u{0015}", "\\u{0016}", "\\u{0017}", "\\u{FFFC}"}:
        return False
    if len(decoded.strip()) < 8:
        return False
    has_hangul = any("\uac00" <= c <= "\ud7a3" for c in decoded)
    has_phrase_space = " " in decoded.strip()
    has_punctuation_phrase = any(c in decoded for c in ":;,.()[]{}")
    return has_hangul or has_phrase_space or has_punctuation_phrase


def scan_file(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8", errors="replace")
    relative = rel(path)
    findings: list[Finding] = []

    for match in TEXT_PROBE_RE.finditer(text):
        literal = match.group("literal")
        if not looks_like_document_text(literal):
            continue
        method = match.group("method")
        line = line_number(text, match.start())
        findings.append(
            Finding(
                "content-text-probe",
                relative,
                f"{method}:{literal}",
                line,
                f'.text.{method}("{literal}")',
            )
        )

    for match in IDENT_RE.finditer(text):
        name = match.group("name")
        if not FIXTURE_IDENTIFIER_RE.search(name):
            continue
        line = line_number(text, match.start())
        findings.append(
            Finding(
                "fixture-identifier",
                relative,
                name,
                line,
                name,
            )
        )

    return findings


def load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        keys.add(stripped)
    return keys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args()

    findings = sorted(f for path in iter_source_files() for f in scan_file(path))
    actual = {finding.key for finding in findings}
    baseline = load_baseline(args.baseline)

    new = sorted(actual - baseline)
    stale = sorted(baseline - actual)

    if not new and not stale:
        if findings:
            print(
                f"renderer overfit check passed with {len(findings)} known baseline finding(s)."
            )
        else:
            print("renderer overfit check passed with no content fingerprints.")
        return 0

    print("renderer overfit check failed.", file=sys.stderr)
    if new:
        print("\nNew renderer overfit finding(s):", file=sys.stderr)
        by_key = {finding.key: finding for finding in findings}
        for key in new:
            finding = by_key[key]
            print(
                f"  {finding.path}:{finding.line}: {finding.rule}: {finding.detail}",
                file=sys.stderr,
            )
            print(f"    baseline key: {key}", file=sys.stderr)
    if stale:
        print("\nStale baseline entrie(s):", file=sys.stderr)
        for key in stale:
            print(f"  {key}", file=sys.stderr)
    print(
        "\nRewrite fixes as structural renderer rules, or remove matching legacy debt "
        "and update the baseline in the same patch.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
