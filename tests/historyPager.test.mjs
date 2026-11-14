import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// The UI history pager (static/js/sessions.js) must keep the viewport pinned
// to the message the user was reading while older pages are prepended. The
// height-delta compensation must measure the box AFTER the page request
// resolves (a live stream frame can append to the bottom while the request is
// in flight and must not be credited to the prepend) AND BEFORE the page is
// rendered: the real renderer (_renderHistoryMessage ->
// _addHistoryMessageWithFullRenderer) APPENDS each bubble to the end of the
// box and the pager loop then moves it to the top. Measuring after that
// render loop would include the new page in `beforeHeight` and the delta
// collapses to zero — the viewport is no longer pinned and jumps up a page.
//
// The harness render stub models that production behavior: it appends to the
// box's end and returns the node, exactly like _addHistoryMessageWithFullRenderer.

const source = await readFile(new URL('../static/js/sessions.js', import.meta.url), 'utf8');

// Slice the pager's dependencies without the whole module:
//  - _historyPageLimit + _historyUrl (no module-level deps beyond API_BASE)
//  - _clearHistoryPager + _installHistoryPager (need document, fetch, window,
//    _historyPager, currentSessionId, _renderHistoryMessage)
const startA = source.indexOf('function _historyPageLimit()');
const endA = source.indexOf('function _addHistoryMessageWithFullRenderer');
const startB = source.indexOf('function _clearHistoryPager()');
const endB = source.indexOf('function _getIncognitoIds()');
assert.ok(startA > 0 && endA > startA && startB > 0 && endB > startB, 'pager source anchors not found');
const pagerSource =
  'var _historyPager = null;\n' +
  source.slice(startA, endA) +
  source.slice(startB, endB);

function makeEl(className, height) {
  return { className, height, nodeType: 1 };
}

function makeBox(initialHeight, existing) {
  const listeners = {};
  const box = {
    scrollTop: 0,
    scrollHeight: initialHeight,
    children: existing || [],
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    removeEventListener(type, fn) {
      listeners[type] = (listeners[type] || []).filter(f => f !== fn);
    },
    querySelector(sel) {
      const wanted = sel.split(',').map(s => s.trim()).filter(Boolean);
      return this.children.find(el => wanted.some(w => el.className && el.className.includes(w.slice(1)))) || null;
    },
    // Real-DOM semantics: if the node is already a child this is a MOVE
    // (no height change); otherwise it's a fresh insertion (adds height).
    insertBefore(el, ref) {
      const existingIdx = this.children.indexOf(el);
      if (existingIdx >= 0) {
        this.children.splice(existingIdx, 1);
      } else {
        this.scrollHeight += el.height;
      }
      const idx = ref ? this.children.indexOf(ref) : 0;
      this.children.splice(idx < 0 ? 0 : idx, 0, el);
    },
    // Models the production renderer: _addHistoryMessageWithFullRenderer
    // appends the bubble to the end of the box (after a temp comment marker)
    // and returns the node. The pager loop then moves it to the top.
    appendChild(el) {
      this.children.push(el);
      this.scrollHeight += el.height;
    },
    get firstChild() { return this.children[0] || null; },
    scroll(type) { (listeners[type] || []).forEach(fn => fn()); },
  };
  return box;
}

function harness({ onFetch = null, page = { offset: 24, limit: 24, has_more_before: true }, streamFrame = 300 } = {}) {
  const box = makeBox(1000, [makeEl('msg-user', 0)]);
  const documentStub = { getElementById: id => (id === 'chat-history' ? box : null) };
  const windowStub = { innerWidth: 1200 };
  const fetchCalls = [];
  const fetchStub = url => {
    fetchCalls.push(url);
    return new Promise(resolve => {
      // A live stream frame arrives at the bottom while the request is in
      // flight — this is the race the compensation must ignore.
      if (streamFrame) {
        const streamEl = makeEl('agent-thread streaming', streamFrame);
        box.children.push(streamEl);
        box.scrollHeight += streamFrame;
      }
      resolve({
        json: async () => ({
          history: [
            { role: 'user', content: 'older-1' },
            { role: 'assistant', content: 'older-2' },
          ],
          offset: 0,
          has_more_before: false,
        }),
      });
    });
    onFetch && onFetch();
  };
  const renderCalls = [];
  // Production-faithful: _addHistoryMessageWithFullRenderer appends to the
  // box's END and returns the node; the pager loop moves it to the top.
  const renderStub = msg => {
    renderCalls.push(msg.content);
    const el = makeEl('msg', 100);
    box.appendChild(el);
    return [el];
  };
  const api = new Function(
    'document', 'fetch', 'window', 'API_BASE', 'currentSessionId', '_renderHistoryMessage',
    'HISTORY_PAGE_LIMIT_DESKTOP', 'HISTORY_PAGE_LIMIT_MOBILE',
    pagerSource + ';return { install: _installHistoryPager, clear: _clearHistoryPager, state: () => _historyPager };'
  )(documentStub, fetchStub, windowStub, 'http://localhost', 'session-1', renderStub, 24, 8);
  api.box = box;
  api.fetchCalls = fetchCalls;
  api.renderCalls = renderCalls;
  api.page = page;
  return api;
}

function triggerScroll(h) {
  h.box.scrollTop = 0;
  h.box.scroll('scroll');
}

test('prepend compensation ignores stream growth that lands while the page request is in flight', async () => {
  const h = harness();
  h.install('session-1', h.page, 'test-model');
  triggerScroll(h);
  await new Promise(r => setTimeout(r, 0));

  // Two 100px history messages were inserted; the 300px stream frame is not
  // part of the prepend and must not move the viewport.
  assert.equal(h.renderCalls.length, 2);
  assert.equal(h.box.scrollTop, 200, 'viewport should shift by exactly the inserted content height');
  assert.equal(h.state().offset, 0);
  assert.equal(h.state().done, true);
});

test('prepend compensation pins the anchor when nothing else changes the box', async () => {
  const h = harness({ page: { offset: 48, limit: 24, has_more_before: true }, streamFrame: 0 });
  h.install('session-1', h.page, 'test-model');
  triggerScroll(h);
  await new Promise(r => setTimeout(r, 0));
  assert.equal(h.box.scrollTop, 200);
  assert.equal(h.fetchCalls.length, 1);
  assert.ok(h.fetchCalls[0].includes('offset=24'), h.fetchCalls[0]);
});

test('single-flight: a second scroll while a page is loading does not refetch', () => {
  const h = harness();
  h.install('session-1', h.page, 'test-model');
  triggerScroll(h);
  h.box.scrollTop = 0;
  h.box.scroll('scroll');
  h.box.scroll('scroll');
  assert.equal(h.fetchCalls.length, 1, 'only one page request per in-flight state');
});

test('no pager is installed when there is nothing older to load', () => {
  const h = harness({ page: { offset: 0, limit: 24, has_more_before: false } });
  h.install('session-1', h.page, 'test-model');
  h.box.scrollTop = 0;
  h.box.scroll('scroll');
  assert.equal(h.fetchCalls.length, 0);
});

test('pager state is cleared and its listener detached', () => {
  const h = harness();
  h.install('session-1', h.page, 'test-model');
  h.clear();
  assert.equal(h.state(), null);
  h.box.scroll('scroll');
  assert.equal(h.fetchCalls.length, 0, 'detached handler must not fetch');
});
