/** OpenAI-compatible LLM client using native fetch */

import type {
  AiderConfig,
  ChatMessage,
  ChatCompletionResponse,
  StreamChunk,
} from "./types.js";

export interface LLMRequestOptions {
  messages: ChatMessage[];
  model?: string;
  maxTokens?: number;
  temperature?: number;
  stream?: boolean;
}

/**
 * Send a chat completion request (non-streaming).
 * Returns the full response.
 */
export async function chatCompletion(
  config: AiderConfig,
  options: LLMRequestOptions,
): Promise<ChatCompletionResponse> {
  const url = `${config.apiBase}/chat/completions`;
  const body = {
    model: options.model ?? config.model,
    messages: options.messages,
    max_tokens: options.maxTokens ?? config.maxTokens,
    temperature: options.temperature ?? config.temperature,
    stream: false,
  };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new LLMError(`LLM request failed (${response.status}): ${text}`, response.status);
  }

  return (await response.json()) as ChatCompletionResponse;
}

/**
 * Send a streaming chat completion request.
 * Yields individual content chunks as they arrive via SSE.
 */
export async function* chatCompletionStream(
  config: AiderConfig,
  options: LLMRequestOptions,
): AsyncGenerator<string, void, undefined> {
  const url = `${config.apiBase}/chat/completions`;
  const body = {
    model: options.model ?? config.model,
    messages: options.messages,
    max_tokens: options.maxTokens ?? config.maxTokens,
    temperature: options.temperature ?? config.temperature,
    stream: true,
  };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new LLMError(`LLM stream request failed (${response.status}): ${text}`, response.status);
  }

  if (!response.body) {
    throw new LLMError("No response body for stream", 0);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;
        const data = trimmed.slice(6);
        if (data === "[DONE]") return;

        try {
          const chunk = JSON.parse(data) as StreamChunk;
          const content = chunk.choices?.[0]?.delta?.content;
          if (content) {
            yield content;
          }
        } catch {
          // Skip malformed JSON chunks
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Send a message and collect full response, supporting both streaming and non-streaming.
 * For streaming, onChunk is called for each piece of content.
 */
export async function sendMessage(
  config: AiderConfig,
  messages: ChatMessage[],
  onChunk?: (chunk: string) => void,
): Promise<string> {
  if (config.stream && onChunk) {
    let fullContent = "";
    for await (const chunk of chatCompletionStream(config, { messages })) {
      fullContent += chunk;
      onChunk(chunk);
    }
    return fullContent;
  } else {
    const response = await chatCompletion(config, { messages });
    const content = response.choices?.[0]?.message?.content ?? "";
    if (onChunk) onChunk(content);
    return content;
  }
}

export class LLMError extends Error {
  constructor(
    message: string,
    public statusCode: number,
  ) {
    super(message);
    this.name = "LLMError";
  }
}
