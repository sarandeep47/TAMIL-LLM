const { test } = require('node:test');
const assert = require('node:assert');

/**
 * Test helper: create a ReadableStream from an array of Uint8Array chunks
 */
function arrayToReadableStream(chunks) {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(chunks[index++]);
      } else {
        controller.close();
      }
    },
  });
}

/**
 * Test helper: convert async iterable to array
 */
async function asyncIterableToArray(iterable) {
  const result = [];
  for await (const item of iterable) {
    result.push(item);
  }
  return result;
}

/**
 * decodeChunks: async generator that decodes Uint8Array chunks as UTF-8
 * Uses TextDecoder with stream: true to handle multibyte sequences across chunk boundaries.
 */
async function* decodeChunks(readable) {
  const reader = readable.getReader();
  const decoder = new TextDecoder('utf-8');

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // Final flush to handle any remaining bytes
        const final = decoder.decode();
        if (final) {
          yield final;
        }
        break;
      }

      // Decode with stream: true to allow incomplete multibyte sequences
      const text = decoder.decode(value, { stream: true });
      if (text) {
        yield text;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

test('Tamil character split across chunks', async () => {
  // JSON: {"event":"token","text":"சென்னை"}
  // UTF-8 bytes: 7b 22 65 76 65 6e 74 22 3a 22 74 6f 6b 65 6e 22 2c 22 74 65 78 74 22 3a 22 e0 ae 9a e0 ae 9f e0 ae 8f 22 7d
  // Tamil "சென்னை" (4 chars) encodes to: e0 ae 9a (ச) e0 ae 9f (ெ) e0 ae 8f (ன) e0 af 88 (ை)
  // e0 ae 9a = 224, 174, 154
  // e0 ae 9f = 224, 174, 159
  // e0 ae 8f = 224, 174, 143
  // e0 af 88 = 224, 175, 136

  const fullJson = '{"event":"token","text":"சென்னை"}';
  const fullBytes = new TextEncoder().encode(fullJson);

  // Split inside the Tamil character: split after first byte of "ெ" (e0)
  // Full: e0 ae 9a e0 ae 9f e0 ae 8f e0 af 88
  // Split: [... e0] [ae 9f e0 ae 8f e0 af 88 ...]
  const splitPoint = fullBytes.indexOf(0xe0, fullBytes.indexOf(0xae) + 2) + 1; // After first e0 of second char

  const chunk1 = fullBytes.slice(0, splitPoint);
  const chunk2 = fullBytes.slice(splitPoint);

  const stream = arrayToReadableStream([chunk1, chunk2]);
  const decoded = await asyncIterableToArray(decodeChunks(stream));
  const result = decoded.join('');

  assert.strictEqual(result, fullJson, `Expected complete JSON with Tamil text, got: ${result}`);
});
