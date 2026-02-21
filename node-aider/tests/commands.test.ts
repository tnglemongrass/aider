import { describe, it, expect, vi } from "vitest";
import { parseCommand, executeCommand, commands } from "../src/commands.js";
import type { CommandContext, AiderConfig, ModelInfo } from "../src/types.js";
import { DEFAULT_CONFIG } from "../src/types.js";

function createMockContext(overrides: Partial<CommandContext> = {}): CommandContext {
  const config: AiderConfig = { ...DEFAULT_CONFIG, apiKey: "test" };
  return {
    config,
    messages: [],
    files: new Set<string>(),
    setModel: vi.fn(),
    setSystemPrompt: vi.fn(),
    getSystemPrompt: () => "test system prompt",
    output: vi.fn(),
    renderMarkdown: vi.fn(),
    listModels: vi.fn(async (): Promise<ModelInfo[]> => [
      { id: "gpt-4o", object: "model" },
      { id: "gpt-4o-mini", object: "model" },
    ]),
    getAgentsContent: () => null,
    clearHistory: vi.fn(),
    quit: vi.fn(),
    ...overrides,
  };
}

describe("parseCommand", () => {
  it("should parse simple command", () => {
    expect(parseCommand("/help")).toEqual(["help", ""]);
  });

  it("should parse command with args", () => {
    expect(parseCommand("/model gpt-4")).toEqual(["model", "gpt-4"]);
  });

  it("should parse command with multiple args", () => {
    expect(parseCommand("/add src/index.ts")).toEqual(["add", "src/index.ts"]);
  });

  it("should return null for non-command input", () => {
    expect(parseCommand("hello world")).toBeNull();
  });

  it("should handle case-insensitive commands", () => {
    expect(parseCommand("/HELP")).toEqual(["help", ""]);
  });

  it("should handle leading whitespace", () => {
    expect(parseCommand("  /help")).toEqual(["help", ""]);
  });
});

describe("commands", () => {
  it("should have all required commands registered", () => {
    const required = [
      "help",
      "model",
      "clear",
      "system",
      "config",
      "quit",
      "exit",
      "add",
      "drop",
      "agents",
    ];
    for (const name of required) {
      expect(commands.has(name), `Missing command: ${name}`).toBe(true);
    }
  });
});

describe("executeCommand", () => {
  it("should execute /help command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("help", "", ctx);
    expect(result).toBe(true);
    expect(ctx.renderMarkdown).toHaveBeenCalled();
  });

  it("should execute /clear command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("clear", "", ctx);
    expect(result).toBe(true);
    expect(ctx.clearHistory).toHaveBeenCalled();
  });

  it("should execute /quit command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("quit", "", ctx);
    expect(result).toBe(true);
    expect(ctx.quit).toHaveBeenCalled();
  });

  it("should execute /exit command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("exit", "", ctx);
    expect(result).toBe(true);
    expect(ctx.quit).toHaveBeenCalled();
  });

  it("should execute /model with name", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("model", "gpt-4", ctx);
    expect(result).toBe(true);
    expect(ctx.setModel).toHaveBeenCalledWith("gpt-4");
  });

  it("should execute /model without name to list models", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("model", "", ctx);
    expect(result).toBe(true);
    expect(ctx.listModels).toHaveBeenCalled();
  });

  it("should execute /system without args to show prompt", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("system", "", ctx);
    expect(result).toBe(true);
    expect(ctx.renderMarkdown).toHaveBeenCalled();
  });

  it("should execute /system with args to set prompt", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("system", "New prompt", ctx);
    expect(result).toBe(true);
    expect(ctx.setSystemPrompt).toHaveBeenCalledWith("New prompt");
  });

  it("should execute /config command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("config", "", ctx);
    expect(result).toBe(true);
    expect(ctx.renderMarkdown).toHaveBeenCalled();
  });

  it("should return false for unknown command", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("nonexistent", "", ctx);
    expect(result).toBe(false);
  });

  it("should execute /agents command with no content", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("agents", "", ctx);
    expect(result).toBe(true);
    expect(ctx.output).toHaveBeenCalledWith("No AGENTS.md loaded.");
  });

  it("should execute /agents command with content", async () => {
    const ctx = createMockContext({
      getAgentsContent: () => "# Agent Guidelines\nBe helpful.",
    });
    const result = await executeCommand("agents", "", ctx);
    expect(result).toBe(true);
    expect(ctx.renderMarkdown).toHaveBeenCalled();
  });

  it("should execute /drop for non-existent file", async () => {
    const ctx = createMockContext();
    const result = await executeCommand("drop", "nonexistent.ts", ctx);
    expect(result).toBe(true);
    expect(ctx.output).toHaveBeenCalledWith(expect.stringContaining("not in context"));
  });
});
