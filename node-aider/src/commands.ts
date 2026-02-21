/** Slash commands for the chat interface */

import * as fs from "node:fs";
import * as path from "node:path";
import type { Command, CommandContext } from "./types.js";

export const commands: Map<string, Command> = new Map();

function register(cmd: Command): void {
  commands.set(cmd.name, cmd);
}

register({
  name: "help",
  description: "Show available commands",
  usage: "/help",
  execute(_args, ctx) {
    const lines: string[] = ["**Available commands:**", ""];
    for (const [, cmd] of commands) {
      lines.push(`  \`${cmd.usage}\` - ${cmd.description}`);
    }
    ctx.renderMarkdown(lines.join("\n"));
  },
});

register({
  name: "model",
  description: "Switch model or list available models",
  usage: "/model [name]",
  async execute(args, ctx) {
    const modelName = args.trim();
    if (!modelName) {
      try {
        const models = await ctx.listModels();
        const lines = models.map((m) => {
          const marker = m.id === ctx.config.model ? " **(current)**" : "";
          return `  - ${m.id}${marker}`;
        });
        ctx.renderMarkdown(`**Available models:**\n${lines.join("\n")}`);
      } catch (err) {
        ctx.output(`Failed to list models: ${err}`);
      }
      return;
    }
    ctx.setModel(modelName);
    ctx.output(`Model switched to: ${modelName}`);
  },
});

register({
  name: "clear",
  description: "Clear chat history",
  usage: "/clear",
  execute(_args, ctx) {
    ctx.clearHistory();
    ctx.output("Chat history cleared.");
  },
});

register({
  name: "system",
  description: "Show or set system prompt",
  usage: "/system [prompt]",
  execute(args, ctx) {
    const newPrompt = args.trim();
    if (!newPrompt) {
      ctx.renderMarkdown(`**Current system prompt:**\n\n${ctx.getSystemPrompt()}`);
      return;
    }
    ctx.setSystemPrompt(newPrompt);
    ctx.output("System prompt updated.");
  },
});

register({
  name: "config",
  description: "Show current configuration",
  usage: "/config",
  execute(_args, ctx) {
    const c = ctx.config;
    const lines = [
      "**Current configuration:**",
      "",
      `  Model: ${c.model}`,
      `  API Base: ${c.apiBase}`,
      `  API Key: ${c.apiKey ? "****" + c.apiKey.slice(-4) : "(not set)"}`,
      `  Max Tokens: ${c.maxTokens}`,
      `  Temperature: ${c.temperature}`,
      `  Stream: ${c.stream}`,
      `  Edit Format: ${c.editFormat}`,
      `  Language: ${c.language}`,
    ];
    ctx.renderMarkdown(lines.join("\n"));
  },
});

register({
  name: "quit",
  description: "Exit aider",
  usage: "/quit",
  execute(_args, ctx) {
    ctx.quit();
  },
});

register({
  name: "exit",
  description: "Exit aider",
  usage: "/exit",
  execute(_args, ctx) {
    ctx.quit();
  },
});

register({
  name: "add",
  description: "Add a file to the chat context",
  usage: "/add <file>",
  execute(args, ctx) {
    const filePath = args.trim();
    if (!filePath) {
      ctx.output("Usage: /add <file>");
      return;
    }
    const resolved = path.resolve(filePath);
    if (!fs.existsSync(resolved)) {
      ctx.output(`File not found: ${filePath}`);
      return;
    }
    ctx.files.add(resolved);
    ctx.output(`Added: ${filePath}`);
  },
});

register({
  name: "drop",
  description: "Remove a file from the chat context",
  usage: "/drop <file>",
  execute(args, ctx) {
    const filePath = args.trim();
    if (!filePath) {
      ctx.output("Usage: /drop <file>");
      return;
    }
    const resolved = path.resolve(filePath);
    if (ctx.files.has(resolved)) {
      ctx.files.delete(resolved);
      ctx.output(`Dropped: ${filePath}`);
    } else {
      ctx.output(`File not in context: ${filePath}`);
    }
  },
});

register({
  name: "agents",
  description: "Show loaded AGENTS.md content",
  usage: "/agents",
  execute(_args, ctx) {
    const content = ctx.getAgentsContent();
    if (content) {
      ctx.renderMarkdown(`**AGENTS.md content:**\n\n${content}`);
    } else {
      ctx.output("No AGENTS.md loaded.");
    }
  },
});

/** Parse a user input string for a command. Returns [commandName, args] or null. */
export function parseCommand(input: string): [string, string] | null {
  const trimmed = input.trim();
  if (!trimmed.startsWith("/")) return null;
  const spaceIdx = trimmed.indexOf(" ");
  if (spaceIdx === -1) {
    return [trimmed.slice(1).toLowerCase(), ""];
  }
  return [trimmed.slice(1, spaceIdx).toLowerCase(), trimmed.slice(spaceIdx + 1)];
}

/** Execute a parsed command. Returns true if command was found and executed. */
export async function executeCommand(
  name: string,
  args: string,
  context: CommandContext,
): Promise<boolean> {
  const cmd = commands.get(name);
  if (!cmd) return false;
  await cmd.execute(args, context);
  return true;
}
