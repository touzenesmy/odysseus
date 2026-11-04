import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// Regression: the agent emits session deep links as `[Name](#session-<id>)`
// (see src/agent_loop.py link convention + create_session result rendering),
// but the three hash resolvers (sessions.js page-load, sessions.js hashchange,
// chat.js _hashSessionCandidate) only stripped OTHER entity prefixes and
// exact-matched `s.id === hashId`. So `#session-<id>` never resolved — the
// `session-` prefix was kept, no session id equals that, and the link silently
// fell through to the last-opened chat. Fix: a single shared normalizer that
// strips the `session-` prefix before the exact match.
const source = await readFile(new URL('../static/js/sessions.js', import.meta.url), 'utf8');

const start = source.indexOf('export function sessionHashId');
assert.notEqual(start, -1, 'sessions.js must export sessionHashId');
const end = source.indexOf('// END_SESSION_HASH_ID', start);
assert.notEqual(end, -1, 'sessionHashId must be terminated by END marker');
const fnSource = source.slice(start, end).replace(/^export\s+/, '');
const sessionHashId = new Function(`${fnSource}\n; return sessionHashId;`)();

test('strips the session- prefix (the actual bug)', () => {
  assert.equal(sessionHashId('session-e3cc8ee9'), 'e3cc8ee9');
  assert.equal(sessionHashId('session-f18b7d8c-a7b0-4671-b290-ca59f58fbbfc'), 'f18b7d8c-a7b0-4671-b290-ca59f58fbbfc');
});

test('passes bare session ids through unchanged', () => {
  assert.equal(sessionHashId('f18b7d8c-a7b0-4671-b290-ca59f58fbbfc'), 'f18b7d8c-a7b0-4671-b290-ca59f58fbbfc');
  assert.equal(sessionHashId('e3cc8ee9'), 'e3cc8ee9');
});

test('still blanks other entity prefixes and the notes-open hash', () => {
  for (const p of ['document', 'note', 'image', 'email', 'event', 'task', 'skill', 'research']) {
    assert.equal(sessionHashId(`${p}-42`), '', `entity prefix ${p}- must blank`);
  }
  assert.equal(sessionHashId('open=notes&note=abc'), '');
});

test('empty/absent hash is empty string', () => {
  assert.equal(sessionHashId(''), '');
  assert.equal(sessionHashId(undefined), '');
  assert.equal(sessionHashId(null), '');
});

test('only strips a session- that is actually a full token (no partial mangle)', () => {
  // A hash that merely *contains* "session-" mid-string is not a session link;
  // leave it to the exact-match fallback rather than corrupting it.
  assert.equal(sessionHashId('notsession-abc'), 'notsession-abc');
});
