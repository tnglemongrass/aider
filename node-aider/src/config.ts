/** Configuration management: CLI args > env vars > config files (YAML) */

import { Command } from "commander";
import { config as dotenvConfig } from "dotenv";
import * as fs from "node:fs";
import * as path from "node:path";
import * as yaml from "js-yaml";
import { AiderConfig, DEFAULT_CONFIG } from "./types.js";

/** Find git root by walking up from startDir */
export function findGitRoot(startDir: string): string | null {
  let dir = path.resolve(startDir);
  while (true) {
    if (fs.existsSync(path.join(dir, ".git"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

/** Load YAML config from a file path, returns partial config or empty object */
export function loadYamlConfig(filePath: string): Partial<AiderConfig> {
  try {
    if (!fs.existsSync(filePath)) return {};
    const content = fs.readFileSync(filePath, "utf-8");
    const parsed = yaml.load(content);
    if (parsed && typeof parsed === "object") {
      return mapYamlToConfig(parsed as Record<string, unknown>);
    }
  } catch {
    // Ignore invalid config files
  }
  return {};
}

/** Map YAML keys (kebab-case) to AiderConfig fields */
function mapYamlToConfig(obj: Record<string, unknown>): Partial<AiderConfig> {
  const result: Partial<AiderConfig> = {};
  if (typeof obj["model"] === "string") result.model = obj["model"];
  if (typeof obj["api-key"] === "string") result.apiKey = obj["api-key"];
  if (typeof obj["api-base"] === "string") result.apiBase = obj["api-base"];
  if (typeof obj["max-tokens"] === "number") result.maxTokens = obj["max-tokens"];
  if (typeof obj["temperature"] === "number") result.temperature = obj["temperature"];
  if (typeof obj["stream"] === "boolean") result.stream = obj["stream"];
  if (typeof obj["edit-format"] === "string") result.editFormat = obj["edit-format"];
  if (typeof obj["language"] === "string") result.language = obj["language"];
  return result;
}

/** Load config from env vars */
export function loadEnvConfig(): Partial<AiderConfig> {
  dotenvConfig();
  const result: Partial<AiderConfig> = {};
  if (process.env.AIDER_MODEL) result.model = process.env.AIDER_MODEL;
  if (process.env.OPENAI_API_KEY) result.apiKey = process.env.OPENAI_API_KEY;
  if (process.env.AIDER_API_KEY) result.apiKey = process.env.AIDER_API_KEY;
  if (process.env.OPENAI_API_BASE) result.apiBase = process.env.OPENAI_API_BASE;
  if (process.env.AIDER_API_BASE) result.apiBase = process.env.AIDER_API_BASE;
  if (process.env.AIDER_MAX_TOKENS) result.maxTokens = parseInt(process.env.AIDER_MAX_TOKENS, 10);
  if (process.env.AIDER_TEMPERATURE) result.temperature = parseFloat(process.env.AIDER_TEMPERATURE);
  if (process.env.AIDER_STREAM) result.stream = process.env.AIDER_STREAM !== "false";
  if (process.env.AIDER_EDIT_FORMAT) result.editFormat = process.env.AIDER_EDIT_FORMAT;
  if (process.env.AIDER_LANGUAGE) result.language = process.env.AIDER_LANGUAGE;
  return result;
}

/** Get ordered list of YAML config file paths to search */
export function getConfigPaths(cwd: string): string[] {
  const paths: string[] = [];
  paths.push(path.join(cwd, ".aider.conf.yml"));
  const gitRoot = findGitRoot(cwd);
  if (gitRoot && gitRoot !== cwd) {
    paths.push(path.join(gitRoot, ".aider.conf.yml"));
  }
  const home = process.env.HOME || process.env.USERPROFILE || "";
  if (home) {
    paths.push(path.join(home, ".aider.conf.yml"));
  }
  return paths;
}

/** Parse CLI arguments and return partial config */
export function parseCLIArgs(argv: string[]): Partial<AiderConfig> & { configPath?: string } {
  const program = new Command();
  program
    .option("--model <model>", "Model name")
    .option("--api-key <key>", "API key")
    .option("--api-base <url>", "API base URL")
    .option("--max-tokens <n>", "Max tokens", parseInt)
    .option("--temperature <n>", "Temperature", parseFloat)
    .option("--no-stream", "Disable streaming")
    .option("--edit-format <format>", "Edit format")
    .option("--config <path>", "Config file path")
    .option("--language <lang>", "Language for responses")
    .allowUnknownOption()
    .parse(argv);

  const opts = program.opts();
  const result: Partial<AiderConfig> & { configPath?: string } = {};

  if (opts.model) result.model = opts.model;
  if (opts.apiKey) result.apiKey = opts.apiKey;
  if (opts.apiBase) result.apiBase = opts.apiBase;
  if (opts.maxTokens) result.maxTokens = opts.maxTokens;
  if (opts.temperature !== undefined) result.temperature = opts.temperature;
  if (opts.stream === false) result.stream = false;
  if (opts.editFormat) result.editFormat = opts.editFormat;
  if (opts.config) result.configPath = opts.config;
  if (opts.language) result.language = opts.language;

  return result;
}

/** Build final configuration: CLI > env > config files > defaults */
export function buildConfig(
  argv: string[] = process.argv,
  cwd: string = process.cwd(),
): AiderConfig {
  // Start with defaults
  const config: AiderConfig = { ...DEFAULT_CONFIG };

  // Layer 1: YAML config files (lowest priority among overrides)
  const configPaths = getConfigPaths(cwd);
  for (const p of configPaths.reverse()) {
    Object.assign(config, loadYamlConfig(p));
  }

  // Layer 2: Environment variables
  Object.assign(config, loadEnvConfig());

  // Layer 3: CLI args (highest priority)
  const cliConfig = parseCLIArgs(argv);

  // If CLI specifies a config file, load it with high priority
  if (cliConfig.configPath) {
    const cliYaml = loadYamlConfig(cliConfig.configPath);
    Object.assign(config, cliYaml);
  }
  delete cliConfig.configPath;
  Object.assign(config, cliConfig);

  // Ensure apiBase doesn't end with /
  config.apiBase = config.apiBase.replace(/\/+$/, "");

  return config;
}
