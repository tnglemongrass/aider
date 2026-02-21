/** System prompts for aider */

const MAIN_SYSTEM_PROMPT = `Act as an expert software developer.
Always use best practices when coding.
Respect and use existing conventions, libraries, etc that are already present in the code base.
Always reply to the user in {language}.`;

const COMMIT_MESSAGE_PROMPT = `Generate a short, conventional commit message for the provided changes.
Use the imperative mood. Be concise. Do not include explanations.
Use conventional commit prefixes: fix, feat, build, chore, ci, docs, style, refactor, perf, test.`;

/**
 * Get the main system prompt with language substitution.
 */
export function getMainSystemPrompt(language: string = "English"): string {
  return MAIN_SYSTEM_PROMPT.replace("{language}", language);
}

/**
 * Get the commit message generation prompt.
 */
export function getCommitMessagePrompt(): string {
  return COMMIT_MESSAGE_PROMPT;
}

/**
 * Build the full system prompt including optional agents context and file context.
 */
export function buildSystemPrompt(options: {
  language?: string;
  agentsContent?: string | null;
  files?: string[];
}): string {
  const parts: string[] = [getMainSystemPrompt(options.language ?? "English")];

  if (options.agentsContent) {
    parts.push(`\n\nProject guidelines (from AGENTS.md):\n${options.agentsContent}`);
  }

  if (options.files && options.files.length > 0) {
    parts.push(`\n\nFiles currently in context:\n${options.files.map((f) => `- ${f}`).join("\n")}`);
  }

  return parts.join("");
}
