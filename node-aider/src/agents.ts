/** AGENTS.md support: load project guidelines from repo or global config */

import * as fs from "node:fs";
import * as path from "node:path";
import { findGitRoot } from "./config.js";

/** Candidate paths for AGENTS.md in a repository */
function getRepoPaths(cwd: string): string[] {
  const paths: string[] = [];
  const gitRoot = findGitRoot(cwd);
  const root = gitRoot ?? cwd;

  paths.push(path.join(root, ".github", "AGENTS.md"));
  paths.push(path.join(root, "AGENTS.md"));
  return paths;
}

/** Get the global AGENTS.md path */
function getGlobalPath(): string {
  const home = process.env.HOME || process.env.USERPROFILE || "";
  return path.join(home, ".aider", "AGENTS.md");
}

/**
 * Load AGENTS.md content. Checks repo paths first, then global.
 * Returns null if no AGENTS.md is found.
 */
export function loadAgentsContent(cwd: string = process.cwd()): string | null {
  const candidates = [...getRepoPaths(cwd), getGlobalPath()];

  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) {
        return fs.readFileSync(candidate, "utf-8");
      }
    } catch {
      // Skip unreadable files
    }
  }

  return null;
}

/**
 * Load skills files from .aider/skills/ directory.
 * Returns concatenated content of all skill files.
 */
export function loadSkills(cwd: string = process.cwd()): string | null {
  const gitRoot = findGitRoot(cwd) ?? cwd;
  const skillsDir = path.join(gitRoot, ".aider", "skills");

  try {
    if (!fs.existsSync(skillsDir)) return null;

    const files = fs.readdirSync(skillsDir).filter((f) => f.endsWith(".md"));
    if (files.length === 0) return null;

    const contents = files.map((f) => {
      const content = fs.readFileSync(path.join(skillsDir, f), "utf-8");
      return `## ${f}\n${content}`;
    });

    return contents.join("\n\n");
  } catch {
    return null;
  }
}

/**
 * Load all agent-related content (AGENTS.md + skills).
 */
export function loadAllAgentContent(cwd: string = process.cwd()): string | null {
  const parts: string[] = [];

  const agents = loadAgentsContent(cwd);
  if (agents) parts.push(agents);

  const skills = loadSkills(cwd);
  if (skills) parts.push(`\n\nSkills:\n${skills}`);

  return parts.length > 0 ? parts.join("") : null;
}
