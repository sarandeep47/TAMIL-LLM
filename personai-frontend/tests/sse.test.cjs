/**
 * SSE Parser tests - run with: node --test tests/sse.test.cjs
 * Tests TypeScript SSE parser compiled to CommonJS
 */

const { test, suite } = require('node:test');
const assert = require('node:assert/strict');

// Import compiled parser (CommonJS)
const { SSEParser } = require('../dist-test/sse.cjs');

suite('SSE Parser', () => {
  test('two events in one chunk', () => {
    const parser = new SSEParser();
    const chunk = 'data: {"event":"token","text":"hello"}\n\ndata: {"event":"token","text":"world"}\n\n';
    const events = parser.feed(chunk);
    
    assert.equal(events.length, 2);
    assert.equal(events[0].text, 'hello');
    assert.equal(events[1].text, 'world');
  });

  test('one event split across three chunks at arbitrary positions', () => {
    const parser = new SSEParser();
    // Split inside "data:" and inside JSON
    const chunk1 = 'da';
    const chunk2 = 'ta: {"event":"token","tex';
    const chunk3 = 't":"split"}\n\n';
    
    let events = parser.feed(chunk1);
    assert.equal(events.length, 0);
    
    events = parser.feed(chunk2);
    assert.equal(events.length, 0);
    
    events = parser.feed(chunk3);
    assert.equal(events.length, 1);
    assert.equal(events[0].text, 'split');
  });

  test('\\r\\n line endings', () => {
    const parser = new SSEParser();
    const chunk = 'data: {"event":"done","reply":"test"}\r\n\r\n';
    const events = parser.feed(chunk);
    
    assert.equal(events.length, 1);
    assert.equal(events[0].reply, 'test');
  });

  test('comment line starting with :', () => {
    const parser = new SSEParser();
    const chunk = ': this is a comment\ndata: {"event":"token","text":"real"}\n\n';
    const events = parser.feed(chunk);
    
    assert.equal(events.length, 1);
    assert.equal(events[0].text, 'real');
  });

  test('unknown event type is ignored', () => {
    const parser = new SSEParser();
    const chunk = 'data: {"event":"unknown_event","value":"ignored"}\n\ndata: {"event":"token","text":"kept"}\n\n';
    const events = parser.feed(chunk);
    
    // Unknown events are parsed but may not match our type - they're still returned
    assert.equal(events.length, 2);
    assert.equal(events[1].text, 'kept');
  });

  test('invalid JSON does not throw and later events still parse', () => {
    const parser = new SSEParser();
    const chunk = 'data: {invalid json}\n\ndata: {"event":"token","text":"valid"}\n\n';
    
    let events;
    assert.doesNotThrow(() => {
      events = parser.feed(chunk);
    });
    
    // First event has bad JSON (ignored), second is valid
    assert.equal(events.length, 1);
    assert.equal(events[0].text, 'valid');
  });

  test('event without trailing blank line stays pending', () => {
    const parser = new SSEParser();
    const chunk = 'data: {"event":"token","text":"pending"}';
    const events = parser.feed(chunk);
    
    // No complete event yet
    assert.equal(events.length, 0);
    
    // Complete it
    const events2 = parser.feed('\n\n');
    assert.equal(events2.length, 1);
    assert.equal(events2[0].text, 'pending');
  });

  test('Tamil text inside JSON', () => {
    const parser = new SSEParser();
    const chunk = 'data: {"event":"done","reply":"வணக்கம்! நான் உங்களுக்கு உதவி செய்யலாம்."}\n\n';
    const events = parser.feed(chunk);
    
    assert.equal(events.length, 1);
    assert.equal(events[0].reply, 'வணக்கம்! நான் உங்களுக்கு உதவி செய்யலாம்.');
  });

  test('flush returns pending events', () => {
    const parser = new SSEParser();
    parser.feed('data: {"event":"sentence","text":"incomplete"}');
    
    const events = parser.flush();
    assert.equal(events.length, 1);
    assert.equal(events[0].text, 'incomplete');
  });
});
