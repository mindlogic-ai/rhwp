#!/usr/bin/env python3
"""Generate Hancom/WebHWP PDF oracles for staged /tmp/diff documents.

This drives the existing WebHWP test iframe on the licensed `webhwp` host. It
copies a staged source into Tomcat's test samples directory, opens it through
the deployed `hwpctrlframe.html`, asks the frame for `requestRender`, and writes
the returned PDF bytes as `hancom.pdf` in the local doc directory.

The script intentionally uses the same WebHWP JS path that FactChat uses for
preview/export verification instead of inventing a separate conversion API.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


RHWP = Path(__file__).resolve().parents[1]
DIFF = Path("/tmp/diff")
DEFAULT_REMOTE_SAMPLES = "/home/rocky/tomcat/webapps/test/samples"
DEFAULT_FRAME_URL = "https://webhwp.mindlogic.ai/test/resources/hwpctrlframe.html"


@dataclass(frozen=True)
class ExportResult:
    pdf: Path
    remote_name: str
    size_bytes: int
    elapsed_sec: float


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=RHWP, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.stderr.write(result.stderr[-2000:])
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return result


def source_path(docdir: Path) -> Path:
    for name in ("source.hwpx", "source.hwp", "source_converted.hwpx", "source_fitted.hwpx"):
        path = docdir / name
        if path.exists():
            return path
    raise SystemExit(f"no source file found in {docdir}")


def ensure_node_deps() -> None:
    script = "require('playwright');"
    result = run(["node", "-e", script], check=False)
    if result.returncode != 0:
        raise SystemExit("node cannot require('playwright'); install/use the repo's Playwright environment")


def upload_source(host: str, source: Path, remote_samples: str) -> str:
    suffix = source.suffix.lower() or ".hwpx"
    remote_name = f"codex-oracle-{uuid.uuid4().hex}{suffix}"
    remote_path = f"{host}:{remote_samples.rstrip('/')}/{remote_name}"
    run(["scp", "-q", str(source), remote_path])
    return remote_name


def cleanup_remote(host: str, remote_samples: str, remote_name: str) -> None:
    remote = f"{remote_samples.rstrip('/')}/{remote_name}"
    run(["ssh", host, "rm", "-f", remote], check=False)


def playwright_script() -> str:
    return r"""
const { chromium } = require('playwright');
const fs = require('fs');

const [frameUrl, openUrl, format, timeoutMsRaw, methodRaw] = process.argv.slice(1);
const timeoutMs = Number(timeoutMsRaw || 90000);
const method = methodRaw || 'download';

function waitForMessage(page, predicate, timeoutMs) {
  return page.evaluate(({ timeoutMs, predicateSource }) => {
    const predicate = new Function('message', `return (${predicateSource})(message);`);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        window.removeEventListener('message', onMessage);
        reject(new Error('timeout_waiting_for_message'));
      }, timeoutMs);
      function onMessage(event) {
        const message = event.data || {};
        let ok = false;
        try { ok = predicate(message); } catch (err) { ok = false; }
        if (!ok) return;
        clearTimeout(timer);
        window.removeEventListener('message', onMessage);
        resolve(message);
      }
      window.addEventListener('message', onMessage);
    });
  }, { timeoutMs, predicateSource: predicate.toString() });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
    acceptDownloads: true,
  });
  page.setDefaultTimeout(timeoutMs);
  await page.setContent(`<!doctype html><meta charset="utf-8">
    <iframe id="hwp" src="${frameUrl}" style="width:1200px;height:820px;border:0"></iframe>`);

  const frameHandle = await page.waitForSelector('#hwp', { timeout: timeoutMs });
  await waitForMessage(page, message => message.type === 'editorReady', timeoutMs);
  await page.evaluate(({ openUrl, format }) => {
    const iframe = document.getElementById('hwp');
    iframe.contentWindow.postMessage({
      type: 'openFile',
      url: openUrl,
      format: format || 'HWPX',
    }, '*');
  }, { openUrl, format });
  const opened = await waitForMessage(page, message => message.type === 'fileOpened', timeoutMs);
  const openOk = opened.result === true || (opened.result && opened.result.result === true);
  if (!openOk) {
    throw new Error(`open_failed:${JSON.stringify(opened)}`);
  }
  const requestId = `render-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  let rendered = null;
  if (method === 'download') {
    const downloadPromise = page.waitForEvent('download', { timeout: timeoutMs });
    await page.evaluate(() => {
      const iframe = document.getElementById('hwp');
      iframe.contentWindow.postMessage({
        type: 'saveAs',
        filename: 'hancom.pdf',
        format: 'PDF',
      }, '*');
    });
    const download = await downloadPromise;
    const downloadPath = await download.path();
    if (!downloadPath) {
      throw new Error('download_missing_path');
    }
    const bytes = fs.readFileSync(downloadPath);
    rendered = {
      base64: bytes.toString('base64'),
      sizeBytes: bytes.length,
    };
  } else {
    await page.evaluate((requestId) => {
      const iframe = document.getElementById('hwp');
      iframe.contentWindow.postMessage({
        type: 'requestRender',
        requestId,
        filename: 'hancom.pdf',
      }, '*');
    }, requestId);
    rendered = await waitForMessage(
      page,
      message => message.type === 'renderReady' && message.requestId === requestId,
      timeoutMs
    );
  }
  await browser.close();
  if (rendered.error) {
    throw new Error(`render_failed:${rendered.error}`);
  }
  if (!rendered.base64) {
    throw new Error('render_missing_base64');
  }
  process.stdout.write(JSON.stringify({
    base64: rendered.base64,
    sizeBytes: rendered.sizeBytes || 0,
  }));
})().catch(async err => {
  console.error(err && err.stack || err);
  process.exit(1);
});
"""


def export_pdf(
    docdir: Path,
    *,
    host: str,
    public_base: str,
    frame_url: str,
    remote_samples: str,
    timeout_ms: int,
    keep_remote: bool,
) -> ExportResult:
    source = source_path(docdir)
    remote_name = upload_source(host, source, remote_samples)
    public_url = f"{public_base.rstrip('/')}/{remote_name}"
    started = time.monotonic()
    try:
        result = run(
            [
                "node",
                "-e",
                playwright_script(),
                frame_url,
                public_url,
                "HWPX" if source.suffix.lower() == ".hwpx" else "HWP",
                str(timeout_ms),
                "download",
            ]
        )
        payload = json.loads(result.stdout)
        data = base64.b64decode(payload["base64"], validate=False)
        if not data.startswith(b"%PDF"):
            raise SystemExit(f"WebHWP render did not return PDF bytes for {docdir.name}")
        pdf = docdir / "hancom.pdf"
        pdf.write_bytes(data)
        return ExportResult(
            pdf=pdf,
            remote_name=remote_name,
            size_bytes=len(data),
            elapsed_sec=time.monotonic() - started,
        )
    finally:
        if not keep_remote:
            cleanup_remote(host, remote_samples, remote_name)


def parse_doc(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = DIFF / raw
    if path.is_file():
        return path.parent
    if not path.exists():
        raise argparse.ArgumentTypeError(f"missing doc directory: {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", nargs="+", type=parse_doc)
    parser.add_argument("--host", default="webhwp")
    parser.add_argument("--remote-samples", default=DEFAULT_REMOTE_SAMPLES)
    parser.add_argument("--public-base", default="https://webhwp.mindlogic.ai/test/samples")
    parser.add_argument("--frame-url", default=DEFAULT_FRAME_URL)
    parser.add_argument("--timeout-ms", type=int, default=120000)
    parser.add_argument("--keep-remote", action="store_true")
    args = parser.parse_args()

    ensure_node_deps()
    for docdir in args.docs:
        result = export_pdf(
            docdir,
            host=args.host,
            public_base=args.public_base,
            frame_url=args.frame_url,
            remote_samples=args.remote_samples,
            timeout_ms=args.timeout_ms,
            keep_remote=args.keep_remote,
        )
        print(
            f"{docdir.name}\t{result.pdf}\t{result.size_bytes} bytes\t"
            f"{result.elapsed_sec:.1f}s\tremote={result.remote_name}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
