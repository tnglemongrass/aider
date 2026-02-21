import { describe, it, expect } from "vitest";
import {
  getMainSystemPrompt,
  getCommitMessagePrompt,
  buildSystemPrompt,
} from "../src/prompts.js";

describe("getMainSystemPrompt", () => {
  it("should return the main system prompt with default language", () => {
    const prompt = getMainSystemPrompt();
    expect(prompt).toContain("Act as an expert software developer");
    expect(prompt).toContain("English");
  });

  it("should substitute custom language", () => {
    const prompt = getMainSystemPrompt("Spanish");
    expect(prompt).toContain("Spanish");
    expect(prompt).not.toContain("{language}");
  });

  it("should contain best practices instruction", () => {
    const prompt = getMainSystemPrompt();
    expect(prompt).toContain("best practices");
  });

  it("should contain conventions instruction", () => {
    const prompt = getMainSystemPrompt();
    expect(prompt).toContain("existing conventions");
  });
});

describe("getCommitMessagePrompt", () => {
  it("should return commit message prompt", () => {
    const prompt = getCommitMessagePrompt();
    expect(prompt).toContain("conventional commit");
    expect(prompt).toContain("imperative mood");
  });

  it("should include commit prefixes", () => {
    const prompt = getCommitMessagePrompt();
    expect(prompt).toContain("fix");
    expect(prompt).toContain("feat");
    expect(prompt).toContain("refactor");
  });
});

describe("buildSystemPrompt", () => {
  it("should build prompt with just language", () => {
    const prompt = buildSystemPrompt({ language: "French" });
    expect(prompt).toContain("French");
    expect(prompt).toContain("Act as an expert software developer");
  });

  it("should include agents content when provided", () => {
    const prompt = buildSystemPrompt({
      agentsContent: "Always write tests first.",
    });
    expect(prompt).toContain("Always write tests first.");
    expect(prompt).toContain("AGENTS.md");
  });

  it("should include file list when provided", () => {
    const prompt = buildSystemPrompt({
      files: ["src/index.ts", "src/config.ts"],
    });
    expect(prompt).toContain("src/index.ts");
    expect(prompt).toContain("src/config.ts");
    expect(prompt).toContain("Files currently in context");
  });

  it("should combine all sections", () => {
    const prompt = buildSystemPrompt({
      language: "German",
      agentsContent: "Be thorough.",
      files: ["main.py"],
    });
    expect(prompt).toContain("German");
    expect(prompt).toContain("Be thorough.");
    expect(prompt).toContain("main.py");
  });

  it("should not include agents section when null", () => {
    const prompt = buildSystemPrompt({ agentsContent: null });
    expect(prompt).not.toContain("AGENTS.md");
  });

  it("should not include files section when empty", () => {
    const prompt = buildSystemPrompt({ files: [] });
    expect(prompt).not.toContain("Files currently in context");
  });
});
