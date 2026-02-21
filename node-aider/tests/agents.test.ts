import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { loadAgentsContent, loadSkills, loadAllAgentContent } from "../src/agents.js";

describe("loadAgentsContent", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "aider-agents-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should return null when no AGENTS.md exists", () => {
    const result = loadAgentsContent(tmpDir);
    expect(result).toBeNull();
  });

  it("should load AGENTS.md from project root", () => {
    fs.writeFileSync(
      path.join(tmpDir, "AGENTS.md"),
      "# Project Guidelines\nBe helpful.",
    );
    const result = loadAgentsContent(tmpDir);
    expect(result).toContain("Project Guidelines");
    expect(result).toContain("Be helpful.");
  });

  it("should load AGENTS.md from .github directory", () => {
    fs.mkdirSync(path.join(tmpDir, ".github"), { recursive: true });
    fs.writeFileSync(
      path.join(tmpDir, ".github", "AGENTS.md"),
      "# GitHub Guidelines",
    );
    const result = loadAgentsContent(tmpDir);
    expect(result).toContain("GitHub Guidelines");
  });

  it("should prefer .github/AGENTS.md over root AGENTS.md", () => {
    fs.mkdirSync(path.join(tmpDir, ".github"), { recursive: true });
    fs.writeFileSync(path.join(tmpDir, ".github", "AGENTS.md"), "GitHub version");
    fs.writeFileSync(path.join(tmpDir, "AGENTS.md"), "Root version");

    const result = loadAgentsContent(tmpDir);
    expect(result).toBe("GitHub version");
  });
});

describe("loadSkills", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "aider-skills-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should return null when no skills directory exists", () => {
    const result = loadSkills(tmpDir);
    expect(result).toBeNull();
  });

  it("should load skill files from .aider/skills/", () => {
    const skillsDir = path.join(tmpDir, ".aider", "skills");
    fs.mkdirSync(skillsDir, { recursive: true });
    fs.writeFileSync(path.join(skillsDir, "coding.md"), "Always write tests.");
    fs.writeFileSync(path.join(skillsDir, "style.md"), "Use TypeScript.");

    const result = loadSkills(tmpDir);
    expect(result).toContain("Always write tests.");
    expect(result).toContain("Use TypeScript.");
    expect(result).toContain("coding.md");
    expect(result).toContain("style.md");
  });

  it("should ignore non-md files", () => {
    const skillsDir = path.join(tmpDir, ".aider", "skills");
    fs.mkdirSync(skillsDir, { recursive: true });
    fs.writeFileSync(path.join(skillsDir, "skill.md"), "MD content");
    fs.writeFileSync(path.join(skillsDir, "notes.txt"), "TXT content");

    const result = loadSkills(tmpDir);
    expect(result).toContain("MD content");
    expect(result).not.toContain("TXT content");
  });
});

describe("loadAllAgentContent", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "aider-all-agents-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should return null when nothing exists", () => {
    const result = loadAllAgentContent(tmpDir);
    expect(result).toBeNull();
  });

  it("should combine AGENTS.md and skills", () => {
    fs.writeFileSync(path.join(tmpDir, "AGENTS.md"), "Agent content");
    const skillsDir = path.join(tmpDir, ".aider", "skills");
    fs.mkdirSync(skillsDir, { recursive: true });
    fs.writeFileSync(path.join(skillsDir, "skill.md"), "Skill content");

    const result = loadAllAgentContent(tmpDir);
    expect(result).toContain("Agent content");
    expect(result).toContain("Skill content");
  });
});
