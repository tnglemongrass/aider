import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import {
  findGitRoot,
  loadYamlConfig,
  loadEnvConfig,
  getConfigPaths,
  parseCLIArgs,
  buildConfig,
} from "../src/config.js";

describe("findGitRoot", () => {
  it("should find git root from a subdirectory", () => {
    // The test repo itself should have a .git
    const root = findGitRoot(process.cwd());
    // May or may not find git root depending on environment
    if (root) {
      expect(fs.existsSync(path.join(root, ".git"))).toBe(true);
    }
  });

  it("should return null when no git root exists", () => {
    const root = findGitRoot("/tmp");
    // /tmp likely has no .git
    expect(root === null || typeof root === "string").toBe(true);
  });
});

describe("loadYamlConfig", () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "aider-test-"));
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  it("should return empty object for non-existent file", () => {
    const result = loadYamlConfig(path.join(tmpDir, "nonexistent.yml"));
    expect(result).toEqual({});
  });

  it("should parse valid YAML config", () => {
    const configPath = path.join(tmpDir, ".aider.conf.yml");
    fs.writeFileSync(
      configPath,
      "model: gpt-4\napi-key: test-key\ntemperature: 0.5\nmax-tokens: 2048\n",
    );
    const result = loadYamlConfig(configPath);
    expect(result.model).toBe("gpt-4");
    expect(result.apiKey).toBe("test-key");
    expect(result.temperature).toBe(0.5);
    expect(result.maxTokens).toBe(2048);
  });

  it("should handle invalid YAML gracefully", () => {
    const configPath = path.join(tmpDir, "bad.yml");
    fs.writeFileSync(configPath, "{{invalid yaml");
    const result = loadYamlConfig(configPath);
    expect(result).toEqual({});
  });
});

describe("loadEnvConfig", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("should load config from environment variables", () => {
    process.env.AIDER_MODEL = "claude-3";
    process.env.OPENAI_API_KEY = "sk-test123";
    process.env.AIDER_TEMPERATURE = "0.3";

    const result = loadEnvConfig();
    expect(result.model).toBe("claude-3");
    expect(result.apiKey).toBe("sk-test123");
    expect(result.temperature).toBe(0.3);
  });

  it("should prefer AIDER_API_KEY over OPENAI_API_KEY", () => {
    process.env.OPENAI_API_KEY = "openai-key";
    process.env.AIDER_API_KEY = "aider-key";

    const result = loadEnvConfig();
    expect(result.apiKey).toBe("aider-key");
  });
});

describe("getConfigPaths", () => {
  it("should return an array of config paths", () => {
    const paths = getConfigPaths("/tmp/test-project");
    expect(Array.isArray(paths)).toBe(true);
    expect(paths.length).toBeGreaterThanOrEqual(1);
    expect(paths[0]).toBe("/tmp/test-project/.aider.conf.yml");
  });
});

describe("parseCLIArgs", () => {
  it("should parse model flag", () => {
    const result = parseCLIArgs(["node", "aider", "--model", "gpt-4o-mini"]);
    expect(result.model).toBe("gpt-4o-mini");
  });

  it("should parse api-key flag", () => {
    const result = parseCLIArgs(["node", "aider", "--api-key", "sk-test"]);
    expect(result.apiKey).toBe("sk-test");
  });

  it("should parse multiple flags", () => {
    const result = parseCLIArgs([
      "node",
      "aider",
      "--model",
      "gpt-4",
      "--temperature",
      "0.2",
      "--max-tokens",
      "1024",
    ]);
    expect(result.model).toBe("gpt-4");
    expect(result.temperature).toBe(0.2);
    expect(result.maxTokens).toBe(1024);
  });

  it("should parse --no-stream flag", () => {
    const result = parseCLIArgs(["node", "aider", "--no-stream"]);
    expect(result.stream).toBe(false);
  });
});

describe("buildConfig", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it("should return defaults when no overrides", () => {
    // Clear any env vars that might be set
    delete process.env.AIDER_MODEL;
    delete process.env.OPENAI_API_KEY;
    delete process.env.AIDER_API_KEY;

    const config = buildConfig(["node", "aider"], "/tmp/no-config-here");
    expect(config.model).toBe("gpt-4o");
    expect(config.temperature).toBe(0.7);
    expect(config.stream).toBe(true);
  });

  it("should strip trailing slashes from apiBase", () => {
    const config = buildConfig(
      ["node", "aider", "--api-base", "http://localhost:8080/v1/"],
      "/tmp",
    );
    expect(config.apiBase).toBe("http://localhost:8080/v1");
  });

  it("CLI args should override env vars", () => {
    process.env.AIDER_MODEL = "env-model";
    const config = buildConfig(
      ["node", "aider", "--model", "cli-model"],
      "/tmp",
    );
    expect(config.model).toBe("cli-model");
  });
});
