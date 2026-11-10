/**
 * Server-Sent Events (SSE) parser - handles decoded text chunks
 * Returns complete events, handles split chunks, multiple events, line endings, partial JSON
 */

export type SSEEvent = 
  | { event: 'stt'; user_text: string; stt_latency_ms: number }
  | { event: 'meta'; route: string; model: string }
  | { event: 'token'; text: string }
  | { event: 'sentence'; index: number; text: string }
  | { event: 'done'; reply: string; ttft_ms: number; first_sentence_ms: number; total_ms: number; route: string; load_ms?: number; prefill_ms?: number; eval_count?: number }
  | { event: 'error'; message: string };

export class SSEParser {
  private buffer = '';

  /**
   * Feed decoded text chunks and return complete events
   * Handles: split events, multiple events in one chunk, \r\n line endings, partial JSON, comment lines
   */
  feed(chunk: string): SSEEvent[] {
    this.buffer += chunk;
    const events: SSEEvent[] = [];

    while (true) {
      // Find next blank line (event separator)
      const doubleNewlineIdx = this.buffer.search(/\r\n\r\n|\n\n|\r\r/);
      
      if (doubleNewlineIdx === -1) {
        // No complete event yet
        break;
      }

      // Extract event block (everything before the blank line)
      const eventBlock = this.buffer.substring(0, doubleNewlineIdx);
      this.buffer = this.buffer.substring(doubleNewlineIdx + 2); // Skip blank line

      // Process event block
      const event = this.parseEventBlock(eventBlock);
      if (event) {
        events.push(event);
      }
    }

    return events;
  }

  /**
   * Parse a single event block (lines before blank line)
   * Format: "field: value\nfield: value\n..."
   */
  private parseEventBlock(block: string): SSEEvent | null {
    const lines = block.split(/\r\n|\n|\r/);
    let dataJson = '';

    for (const line of lines) {
      // Skip comment lines and empty lines
      if (line.startsWith(':') || !line.trim()) {
        continue;
      }

      // Extract "data: ..." line
      if (line.startsWith('data:')) {
        const dataStr = line.substring(5).trim();
        dataJson = dataStr;
        break;
      }
    }

    if (!dataJson) {
      return null;
    }

    try {
      return JSON.parse(dataJson) as SSEEvent;
    } catch {
      // Ignore malformed JSON
      return null;
    }
  }

  /**
   * Flush any remaining data (end of stream)
   */
  flush(): SSEEvent[] {
    const events: SSEEvent[] = [];
    
    if (this.buffer.trim()) {
      const event = this.parseEventBlock(this.buffer);
      if (event) {
        events.push(event);
      }
    }

    this.buffer = '';
    return events;
  }
}
