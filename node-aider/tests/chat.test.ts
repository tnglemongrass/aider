import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AiderConfig, ChatCompletionResponse } from "../src/types.js";
import { DEFAULT_CONFIG } from "../src/types.js";
import { ChatSession } from "../src/chat.js";

const mockConfig: AiderConfig = {
  ...DEFAULT_CONFIG,
  apiKey: "test-key",
  apiBase: "http://localhost:11434/v1",
  model: "test-model",
  stream: false,
};

function mockFetchResponse(content: string): Response {
  const body: ChatCompletionResponse = {
    id: "test",
    object: "chat.completion",
    created: Date.now(),
    model: "test-model",
    choices: [
      {
        index: 0,
        message: { role: "assistant", content },
        finish_reason: "stop",
      },
    ],
  };

  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: new Headers(),
    text: async () => JSON.stringify(body),
    json: async () => body,
    body: null,
    redirected: false,
    type: "basic" as ResponseType,
    url: "",
    clone: () => mockFetchResponse(content),
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
    bytes: async () => new Uint8Array(),
  } as Response;
}

describe("ChatSession", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should initialize with system prompt", () => {
    const session = new ChatSession(mockConfig, "/tmp");
    const prompt = session.getSystemPrompt();
    expect(prompt).toContain("Act as an expert software developer");
    expect(prompt).toContain("English");
  });

  it("should build messages with system prompt", () => {
    const session = new ChatSession(mockConfig, "/tmp");
    const messages = session.buildMessages("Hello");
    expect(messages[0].role).toBe("system");
    expect(messages[0].content).toContain("Act as an expert software developer");
    expect(messages[messages.length - 1]).toEqual({
      role: "user",
      content: "Hello",
    });
  });

  it("should store conversation history after send", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse("Hi there!"));

    const session = new ChatSession(mockConfig, "/tmp");
    // Suppress stdout
    const writeSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);

    await session.send("Hello");

    writeSpy.mockRestore();

    expect(session.messages).toHaveLength(2);
    expect(session.messages[0]).toEqual({ role: "user", content: "Hello" });
    expect(session.messages[1]).toEqual({
      role: "assistant",
      content: "Hi there!",
    });
  });

  it("should clear history", async () => {
    vi.mocked(fetch).mockResolvedValue(mockFetchResponse("Hi!"));

    const session = new ChatSession(mockConfig, "/tmp");
    const writeSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);

    await session.send("Hello");
    expect(session.messages).toHaveLength(2);

    session.clearHistory();
    expect(session.messages).toHaveLength(0);

    writeSpy.mockRestore();
  });

  it("should include file context in messages when files are added", () => {
    const session = new ChatSession(mockConfig, "/tmp");
    // Add a file that doesn't exist - it should appear as "unreadable"
    session.files.add("/tmp/nonexistent-test-file.ts");

    const messages = session.buildMessages("What is this?");
    const systemMsg = messages[0].content;
    expect(systemMsg).toContain("/tmp/nonexistent-test-file.ts");
  });

  it("should handle command processing", async () => {
    const session = new ChatSession(mockConfig, "/tmp");
    const consoleSpy = vi.spyOn(console, "log").mockImplementation(() => {});

    await session.processInput("/clear");

    consoleSpy.mockRestore();
    // After /clear, history should be empty
    expect(session.messages).toHaveLength(0);
  });

  it("should set custom system prompt", () => {
    const session = new ChatSession(mockConfig, "/tmp");
    session.setSystemPrompt("Custom prompt");
    expect(session.getSystemPrompt()).toBe("Custom prompt");
  });

  it("should create a valid command context", () => {
    const session = new ChatSession(mockConfig, "/tmp");
    const ctx = session.createCommandContext();

    expect(ctx.config).toEqual(mockConfig);
    expect(ctx.messages).toBe(session.messages);
    expect(ctx.files).toBe(session.files);
    expect(typeof ctx.setModel).toBe("function");
    expect(typeof ctx.quit).toBe("function");
  });
});
