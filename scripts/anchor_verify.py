#!/usr/bin/env python3
"""anchor-verify: the two-part audit protocol for specs/instance/*-anchor.md.

Part 1 -- anchor check (always on): for every row of the "Hashes at audit time"
table, run `git hash-object` and compare the first N hex chars. A match means the
file is untouched, so the recorded invariants can be trusted as-is. A mismatch
means the file was edited since the audit.

Part 2 -- delta (`--delta`): for each row that changed or went missing, print
only what moved since the recorded commit: the commits that touched the file
(`git rev-list`/`git log`) and the `git diff --stat`, plus the full hunks with
`--patch`. That is the "read only the diff since the audit commit" step -- a
re-audit stays cheap instead of re-reading the file from scratch.

Usage:
    python3 scripts/anchor_verify.py [ANCHOR.md] [--quiet] [--json]
    python3 scripts/anchor_verify.py --delta [--since REV] [--patch] [-n N]

The delta baseline is `--since REV` if given (which implies --delta), else the
commit named in the anchor's "committed blobs at `...`" prose, else HEAD.

Exit codes: 0 = every row matches; 1 = at least one changed/missing; 2 = error.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_ANCHOR = "specs/instance/voice-audit-anchor.md"
ROW_RE = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|\s*$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{6,40}$")
NOTE_RE = re.compile(r"\s*\(.*\)\s*$")  # strips "(TTS section only)" and friends
# the anchor records the commit the table was stamped at, e.g.
# "verified equal to the committed blobs at\n`cb25895d`".
COMMIT_RE = re.compile(r"committed blobs at\s*`([0-9a-fA-F]{6,40})`")
DEFAULT_COMMIT_LIMIT = 20


def repo_root() -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("error: not inside a git work tree")
    return Path(out.stdout.strip())


def parse_rows(text: str):
    """Yield (repo_relative_path, expected_first_8) for each hash-table data row."""
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        raw_file, expected, _audit = (c.strip() for c in m.groups())
        # strip backticks first so a "(note)" is removed regardless of whether
        # it sits inside or outside the code span.
        path = NOTE_RE.sub("", raw_file.replace("`", "")).strip().strip("* ")
        expected = expected.replace("`", "").strip().strip("* ")
        if path.lower() == "file" or not HEX_RE.match(expected):
            continue  # header row or the |---|---| separator
        rows.append((path, expected.lower()))
    return rows


def hash_object(root: Path, rel: str):
    out = subprocess.run(["git", "-C", str(root), "hash-object", "--", rel],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None  # missing / unreadable
    return out.stdout.strip() or None


def git(root: Path, *args):
    out = subprocess.run(["git", "-C", str(root), *args],
                         capture_output=True, text=True)
    return out.returncode, out.stdout, out.stderr


def resolve_baseline(root: Path, explicit, text: str):
    """Return (full_sha, short_sha) for the delta baseline."""
    if explicit:
        rev = explicit
    else:
        m = COMMIT_RE.search(text)
        rev = m.group(1) if m else "HEAD"
    rc, out, _err = git(root, "rev-parse", "--verify", "--quiet",
                        f"{rev}^{{commit}}")
    if rc != 0:
        sys.exit(f"error: baseline revision not found: {rev}")
    full = out.strip()
    return full, full[:12]


def file_delta(root: Path, since: str, rel: str, limit: int, want_patch: bool,
               status: str) -> dict:
    """What moved for one file: commits touching it + diff vs the worktree."""
    d = {"file": rel, "status": status, "commits": [], "commit_count": 0,
         "stat": "", "patch": None}
    _, out, _ = git(root, "rev-list", "--count", f"{since}..HEAD", "--", rel)
    d["commit_count"] = int(out.strip() or 0)
    _, out, _ = git(root, "log", f"--max-count={limit}", "--oneline",
                    f"{since}..HEAD", "--", rel)
    d["commits"] = [ln for ln in out.splitlines() if ln.strip()]
    # diff against the working tree (single revision) so uncommitted edits show.
    _, out, _ = git(root, "diff", "--stat", since, "--", rel)
    d["stat"] = out.strip()
    if want_patch:
        _, out, _ = git(root, "diff", since, "--", rel)
        d["patch"] = out.rstrip("\n")
    return d


def _print_delta(delta: dict) -> None:
    since = delta["since"][:12]
    print()
    print(f"delta since {since}:")
    for d in delta["files"]:
        gone = "  (missing from the working tree)" if d["status"] == "missing" else ""
        print(f"\n  -- {d['file']}{gone}")
        n = d["commit_count"]
        if n:
            shown = "" if len(d["commits"]) >= n else f" (first {len(d['commits'])})"
            print(f"     {n} commit(s) since {since}{shown}:")
            for line in d["commits"]:
                print(f"       {line}")
        else:
            print(f"     no committed change since {since} (working-tree edit only)")
        for line in d["stat"].splitlines():
            print(f"     {line}")
        if d["patch"]:
            print()
            for line in d["patch"].splitlines():
                print(f"     {line}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("anchor", nargs="?", default=DEFAULT_ANCHOR,
                    help=f"anchor markdown (default: {DEFAULT_ANCHOR})")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="print only rows that changed or are missing")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("-d", "--delta", action="store_true",
                    help="part 2: for drifted rows, show the diff since the "
                         "recorded commit instead of a full re-read")
    ap.add_argument("--since", metavar="REV",
                    help="baseline revision for --delta (implies --delta; "
                         "default: the anchor's recorded commit, else HEAD)")
    ap.add_argument("-p", "--patch", action="store_true",
                    help="with --delta, include full unified diff hunks")
    ap.add_argument("-n", "--max-commits", type=int, default=DEFAULT_COMMIT_LIMIT,
                    metavar="N", help=f"with --delta, list at most N commits "
                                      f"(default {DEFAULT_COMMIT_LIMIT})")
    args = ap.parse_args(argv)
    if args.since:
        args.delta = True

    root = repo_root()
    doc = Path(args.anchor)
    if not doc.is_absolute():
        doc = root / doc
    if not doc.is_file():
        sys.exit(f"error: anchor not found: {doc}")

    text = doc.read_text()
    rows = parse_rows(text)
    if not rows:
        sys.exit(f"error: no hash rows parsed from {doc}")

    results = []
    for rel, expected in rows:
        digest = hash_object(root, rel)
        if digest is None:
            status, actual = "missing", None
        else:
            actual = digest[: len(expected)]
            status = "ok" if actual == expected else "changed"
        results.append({"file": rel, "expected": expected,
                        "actual": actual, "status": status})

    counts = {k: sum(r["status"] == k for r in results)
              for k in ("ok", "changed", "missing")}
    rel_doc = doc.relative_to(root) if doc.is_relative_to(root) else doc
    drift = [r for r in results if r["status"] != "ok"]

    delta = None
    if args.delta and drift:
        since, _short = resolve_baseline(root, args.since, text)
        delta = {"since": since, "files": [
            file_delta(root, since, r["file"], args.max_commits, args.patch,
                       r["status"])
            for r in drift]}

    if args.json:
        payload = {"anchor": str(rel_doc), "counts": counts, "rows": results}
        if delta:
            payload["delta"] = delta
        print(json.dumps(payload, indent=2))
    else:
        label = {"ok": "ok", "changed": "CHANGED", "missing": "MISSING"}
        for r in results:
            if args.quiet and r["status"] == "ok":
                continue
            if r["status"] == "ok":
                note = r["expected"]
            elif r["status"] == "changed":
                note = f"{r['expected']} -> {r['actual']}"
            else:
                note = f"{r['expected']} (file gone)"
            print(f"  {label[r['status']]:7}  {note:22}  {r['file']}")
        print(f"{counts['ok']} ok, {counts['changed']} changed, "
              f"{counts['missing']} missing  ({rel_doc})")
        if delta:
            _print_delta(delta)
        elif drift and not args.delta:
            print(f"  hint: {len(drift)} file(s) drifted -- re-run with "
                  f"--delta to see just what moved")

    return 0 if not (counts["changed"] or counts["missing"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
