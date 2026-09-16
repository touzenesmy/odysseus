"""Regression guard: deleting a message removes the WHOLE turn.

2026-09-15: deleteMessage() paired the clicked bubble with only the FIRST
assistant bubble of the turn (aiIndex, single id). One turn can span several
assistant rows (a tool-approval question row + the response row; interrupted
then continued runs). Deleting such a turn left the extra assistant rows in
the DB, so after a refresh the AI output reappeared with no user prompt
before it — orphaned assistant rows that also feed the model context.

deleteMessage must now remove every bubble (and every distinct dataset.dbId)
from the owning user bubble to the next user bubble. chat.js pulls in browser
globals so it can't run under node; guard at the source, mirroring
test_delete_message_no_session.py.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "static/js/chat.js"


def _delete_message_body() -> str:
    text = SRC.read_text(encoding="utf-8")
    start = text.index("export async function deleteMessage(")
    rest = text[start:]
    m = re.search(r"\n  export (async )?function ", rest[1:])
    return rest[: m.start() + 1] if m else rest


def test_no_single_ai_bubble_pairing():
    body = _delete_message_body()
    # The old bug: pairing stopped at the first AI bubble (aiIndex) and only
    # ever pushed that bubble's dbId.
    assert "let aiIndex = -1;" not in body, (
        "deleteMessage must not pair with a single (first) AI bubble only"
    )
    assert not re.search(r"const aid = allMsgs\[aiIndex\]", body), (
        "deleteMessage must not read a single AI bubble's dbId"
    )


def test_collects_ids_across_whole_turn():
    body = _delete_message_body()
    # Turn end = next user bubble (exclusive), from the owning user bubble.
    assert re.search(r"for \(let i = \(userIndex >= 0 \? userIndex : clickedIndex\) \+ 1;", body), (
        "turn scan must start after the owning user bubble"
    )
    # Every bubble in the turn range is removed and contributes its dbId.
    assert re.search(r"for \(let el = startEl; el && el !== endEl; el = el\.nextElementSibling\)", body), (
        "must walk every element from the turn start to the next user bubble"
    )
    # Ids are deduplicated (continuation bubbles share their row's id).
    assert "seenIds" in body, "dbId collection must dedupe shared row ids"


def test_orphaned_ai_bubble_still_deletes():
    body = _delete_message_body()
    # An AI bubble with no user bubble before it (its prompt was already
    # deleted) must not bail: userIndex stays -1 and the walk starts at the
    # clicked bubble.
    assert re.search(r"let userIndex = clickedIsUser \? clickedIndex : -1;", body)
    assert re.search(r"const startEl = userIndex >= 0 \? allMsgs\[userIndex\] : allMsgs\[clickedIndex\];", body), (
        "orphaned AI bubble must start its own deletion range at itself"
    )
    # And the DOM-removal / server path is still guarded on ids, not on a
    # found user bubble.
    assert re.search(r"!msgIds\.length\s*\|\|\s*!sessionId", body)
