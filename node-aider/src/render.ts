/** Markdown terminal rendering */

import { Marked } from "marked";
import { markedTerminal } from "marked-terminal";
import chalk from "chalk";

let renderer: Marked | null = null;

function getRenderer(): Marked {
  if (!renderer) {
    renderer = new Marked();
    renderer.use(markedTerminal() as object);
  }
  return renderer;
}

/** Render markdown text for terminal display */
export function renderMarkdown(text: string): string {
  const r = getRenderer();
  const result = r.parse(text);
  if (typeof result === "string") return result;
  // Should not happen with synchronous marked, but handle gracefully
  return text;
}

/** Render a streaming chunk - for progressive output during streaming */
export function renderStreamChunk(chunk: string): string {
  // During streaming, we output raw text; full markdown render happens after
  return chunk;
}

/** Format an info message */
export function formatInfo(text: string): string {
  return chalk.cyan(`ℹ ${text}`);
}

/** Format a warning message */
export function formatWarning(text: string): string {
  return chalk.yellow(`⚠ ${text}`);
}

/** Format an error message */
export function formatError(text: string): string {
  return chalk.red(`✖ ${text}`);
}

/** Format a success message */
export function formatSuccess(text: string): string {
  return chalk.green(`✔ ${text}`);
}

/** Format a prompt label */
export function formatPrompt(model: string): string {
  return chalk.bold.blue(`aider (${model})> `);
}
