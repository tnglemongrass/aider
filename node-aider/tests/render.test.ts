import { describe, it, expect } from "vitest";
import {
  renderMarkdown,
  formatInfo,
  formatWarning,
  formatError,
  formatSuccess,
  formatPrompt,
} from "../src/render.js";

describe("renderMarkdown", () => {
  it("should render plain text", () => {
    const result = renderMarkdown("Hello world");
    expect(result).toContain("Hello world");
  });

  it("should render headings", () => {
    const result = renderMarkdown("# Title");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("should render code blocks", () => {
    const result = renderMarkdown("```js\nconsole.log('hi');\n```");
    expect(result).toContain("console.log");
  });

  it("should render bullet lists", () => {
    const result = renderMarkdown("- item 1\n- item 2\n- item 3");
    expect(result).toContain("item 1");
    expect(result).toContain("item 2");
  });
});

describe("formatInfo", () => {
  it("should format info message", () => {
    const result = formatInfo("test message");
    expect(result).toContain("test message");
  });
});

describe("formatWarning", () => {
  it("should format warning message", () => {
    const result = formatWarning("warning message");
    expect(result).toContain("warning message");
  });
});

describe("formatError", () => {
  it("should format error message", () => {
    const result = formatError("error message");
    expect(result).toContain("error message");
  });
});

describe("formatSuccess", () => {
  it("should format success message", () => {
    const result = formatSuccess("success message");
    expect(result).toContain("success message");
  });
});

describe("formatPrompt", () => {
  it("should include model name in prompt", () => {
    const result = formatPrompt("gpt-4o");
    expect(result).toContain("gpt-4o");
  });
});
