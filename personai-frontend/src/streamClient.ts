/**
 * Streaming client for /api/chat-stream and /api/voice-turn-stream
 * Uses fetch, response.body.getReader(), and TextDecoder with AbortController
 */

import { SSEParser, type SSEEvent } from './sse';
import { API_BASE } from './constants';

export interface StreamHandlers {
  onEvent?: (event: SSEEvent) => void;
  onError?: (message: string) => void;
  onComplete?: () => void;
}

/**
 * Decode an async iterable of Uint8Array chunks using TextDecoder with streaming mode.
 * Yields decoded strings, handling multibyte UTF-8 sequences that span chunks.
 */
export async function* decodeChunks(
  readable: ReadableStream<Uint8Array>
): AsyncGenerator<string, void, unknown> {
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

/**
 * Stream a text chat request
 */
export async function streamChat(
  text: string,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/chat-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
      signal,
    });

    if (!response.ok) {
      handlers.onError?.(`HTTP ${response.status}: ${response.statusText}`);
      return;
    }

    if (!response.body) {
      handlers.onError?.('No response body');
      return;
    }

    await consumeStream(response.body, handlers);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      // Abort is not an error
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    handlers.onError?.(message);
  }
}

/**
 * Stream a voice input request
 */
export async function streamVoiceTurn(
  blob: Blob,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  try {
    const formData = new FormData();
    formData.append('file', blob, 'audio.wav');

    const response = await fetch(`${API_BASE}/voice-turn-stream`, {
      method: 'POST',
      body: formData,
      signal,
    });

    if (!response.ok) {
      handlers.onError?.(`HTTP ${response.status}: ${response.statusText}`);
      return;
    }

    if (!response.body) {
      handlers.onError?.('No response body');
      return;
    }

    await consumeStream(response.body, handlers);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return;
    }
    const message = error instanceof Error ? error.message : String(error);
    handlers.onError?.(message);
  }
}

/**
 * Consume a ReadableStream, parse SSE events, and call handlers
 */
async function consumeStream(
  body: ReadableStream<Uint8Array>,
  handlers: StreamHandlers
): Promise<void> {
  const parser = new SSEParser();

  try {
    for await (const text of decodeChunks(body)) {
      // Parse events from chunk
      const events = parser.feed(text);
      for (const event of events) {
        handlers.onEvent?.(event);
      }
    }

    // Flush any remaining events
    const events = parser.flush();
    for (const event of events) {
      handlers.onEvent?.(event);
    }

    handlers.onComplete?.();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return;
    }
    throw error;
  }
}
