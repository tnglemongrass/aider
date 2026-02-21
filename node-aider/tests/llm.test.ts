import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AiderConfig, ChatCompletionResponse, StreamChunk } from "../src/types.js";
import { chatCompletion, chatCompletionStream, sendMessage, LLMError } from "../src/llm.js";
import { DEFAULT_CONFIG } from "../src/types.js";

const mockConfig: AiderConfig = {
  ...DEFAULT_CONFIG,
  apiKey: "test-key",
  apiBase: "http://localhost:11434/v1",
  model: "test-model",
  stream: false,
};

function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    headers: new Headers(),
    text: async () => JSON.stringify(body),
    json: async () => body,
    body: null,
    redirected: false,
    type: "basic" as ResponseType,
    url: "",
    clone: () => mockResponse(body, status),
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
    bytes: async () => new Uint8Array(),
  } as Response;
}

function mockStreamResponse(chunks: string[]): Response {
  const sseData = chunks
    .map((c) => {
      const chunk: StreamChunk = {
        id: "test",
        object: "chat.completion.chunk",
        created: Date.now(),
        model: "test-model",
        choices: [{ index: 0, delta: { content: c }, finish_reason: null }],
      };
      return `data: ${JSON.stringify(chunk)}`;
    })
    .join("\n\n");

  const fullData = sseData + "\n\ndata: [DONE]\n\n";
  const encoder = new TextEncoder();
  const encoded = encoder.encode(fullData);

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoded);
      controller.close();
    },
  });

  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    text: async () => fullData,
    json: async () => ({}),
    body: stream,
    redirected: false,
    type: "basic" as ResponseType,
    url: "",
    clone: () => mockStreamResponse(chunks),
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
    bytes: async () => new Uint8Array(),
  } as Response;
}

describe("chatCompletion", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should send a chat completion request", async () => {
    const mockBody: ChatCompletionResponse = {
      id: "chatcmpl-test",
      object: "chat.completion",
      created: Date.now(),
      model: "test-model",
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: "Hello!" },
          finish_reason: "stop",
        },
      ],
    };

    vi.mocked(fetch).mockResolvedValue(mockResponse(mockBody));

    const result = await chatCompletion(mockConfig, {
      messages: [{ role: "user", content: "Hi" }],
    });

    expect(result.choices[0].message.content).toBe("Hello!");
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:11434/v1/chat/completions",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-key",
        }),
      }),
    );
  });

  it("should throw LLMError on non-OK response", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockResponse({ error: "unauthorized" }, 401),
    );

    await expect(
      chatCompletion(mockConfig, {
        messages: [{ role: "user", content: "Hi" }],
      }),
    ).rejects.toThrow(LLMError);
  });

  it("should use custom model name without prefixes", async () => {
    const mockBody: ChatCompletionResponse = {
      id: "test",
      object: "chat.completion",
      created: Date.now(),
      model: "my-custom-model",
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: "OK" },
          finish_reason: "stop",
        },
      ],
    };

    vi.mocked(fetch).mockResolvedValue(mockResponse(mockBody));

    await chatCompletion(mockConfig, {
      messages: [{ role: "user", content: "Hi" }],
      model: "my-custom-model",
    });

    const callBody = JSON.parse(
      (vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string,
    );
    expect(callBody.model).toBe("my-custom-model");
  });
});

describe("chatCompletionStream", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should yield streamed content chunks", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockStreamResponse(["Hello", " ", "world", "!"]),
    );

    const streamConfig = { ...mockConfig, stream: true };
    const chunks: string[] = [];

    for await (const chunk of chatCompletionStream(streamConfig, {
      messages: [{ role: "user", content: "Hi" }],
    })) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual(["Hello", " ", "world", "!"]);
  });

  it("should throw on non-OK response", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockResponse({ error: "bad request" }, 400),
    );

    const gen = chatCompletionStream(mockConfig, {
      messages: [{ role: "user", content: "Hi" }],
    });

    await expect(gen.next()).rejects.toThrow(LLMError);
  });
});

describe("sendMessage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should return full response for non-streaming", async () => {
    const mockBody: ChatCompletionResponse = {
      id: "test",
      object: "chat.completion",
      created: Date.now(),
      model: "test-model",
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: "Response text" },
          finish_reason: "stop",
        },
      ],
    };

    vi.mocked(fetch).mockResolvedValue(mockResponse(mockBody));

    const nonStreamConfig = { ...mockConfig, stream: false };
    const result = await sendMessage(nonStreamConfig, [
      { role: "user", content: "Hello" },
    ]);

    expect(result).toBe("Response text");
  });

  it("should collect streaming chunks and call onChunk", async () => {
    vi.mocked(fetch).mockResolvedValue(mockStreamResponse(["a", "b", "c"]));

    const streamConfig = { ...mockConfig, stream: true };
    const chunks: string[] = [];

    const result = await sendMessage(
      streamConfig,
      [{ role: "user", content: "Hello" }],
      (chunk) => chunks.push(chunk),
    );

    expect(result).toBe("abc");
    expect(chunks).toEqual(["a", "b", "c"]);
  });
});
