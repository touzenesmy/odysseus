#!/usr/bin/env bash
#
# voice-audit-bg -- run the two-part voice-audit anchor protocol as a DETACHED job.
#
# The prompt this replaces (previously pasted into chat every time):
#
#     Run the two-part audit on specs/instance/voice-audit-anchor.md:
#       Part 1 -- verify the anchor hash table against the working tree.
#       Part 2 -- show only what changed since the audit commit.
#
# It does NOT re-implement any of that. It reuses the existing verifier,
# scripts/anchor_verify.py (Part 1 anchor check + Part 2 delta), and wraps it so
# the whole thing can be launched in the background and leaves a report behind.
#
# Usage:
#     scripts/voice-audit-bg.sh [--patch] [-n N] [--since REV]
#     ANCHOR=specs/instance/other-anchor.md scripts/voice-audit-bg.sh
#
# Detached, from the harness:
#     #!bg scripts/voice-audit-bg.sh --patch
#
# Output:
#     reports/voice-audit-<UTC-stamp>.txt   (full report)
#     one SUMMARY / REPORT / EXIT block on stdout, exit code = verifier's.
#
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ANCHOR="${ANCHOR:-specs/instance/voice-audit-anchor.md}"
OUTDIR="$ROOT/reports"
mkdir -p "$OUTDIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUTDIR/voice-audit-$STAMP.txt"
RAW="$OUT.tmp"

# Part 1 (anchor check) + Part 2 (delta) in one pass: --delta implies the check.
PASS=""
for a in "$@"; do [ "$a" = "--patch" ] || PASS="$PASS $a"; done
python3 scripts/anchor_verify.py "$ANCHOR" --delta --patch $PASS >"$RAW" 2>&1
rc=$?

{
  echo "# voice-audit  $STAMP"
  echo "# anchor:      $ANCHOR"
  echo "# HEAD:        $(git rev-parse --short HEAD 2>/dev/null || echo none)"
  echo "# command:     python3 scripts/anchor_verify.py $ANCHOR --delta --patch${PASS:+ $PASS}"
  echo
  cat "$RAW"
} >"$OUT"
rm -f "$RAW"

echo "SUMMARY: $(grep -m1 -E '[0-9]+ ok, [0-9]+ changed, [0-9]+ missing' "$OUT" || echo 'no summary line')"
echo "REPORT:  $OUT"
echo "EXIT:    $rc   (0 = all rows match, 1 = change/missing, 2 = error)"
exit "$rc"
