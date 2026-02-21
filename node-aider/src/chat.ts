/** Chat session manager */

import * as fs from "node:fs";
import * as readline from "node:readline";
import type { AiderConfig, ChatMessage, CommandContext, ModelInfo } from "./types.js";
import { sendMessage } from "./llm.js";
import { fetchModels } from "./models.js";
import { loadAllAgentContent } from "./agents.js";
import { buildSystemPrompt } from "./prompts.js";
import { parseCommand, executeCommand } from "./commands.js";
import {
  renderMarkdown,
  formatInfo,
  formatError,
  formatPrompt,
} from "./render.js";

export class ChatSession {
  public messages: ChatMessage[] = [];
  public files: Set<string> = new Set();
  private systemPrompt: string;
  private agentsContent: string | null;
  private running = true;

  constructor(
    public config: AiderConfig,
    private cwd: string = process.cwd(),
  ) {
    this.agentsContent = loadAllAgentContent(cwd);
    this.systemPrompt = buildSystemPrompt({
      language: config.language,
      agentsContent: this.agentsContent,
    });
  }

  /** Get the current system prompt */
  getSystemPrompt(): string {
    return this.systemPrompt;
  }

  /** Set a custom system prompt */
  setSystemPrompt(prompt: string): void {
    this.systemPrompt = prompt;
  }

  /** Build messages array including system prompt and file contents */
  buildMessages(userMessage: string): ChatMessage[] {
    const fileContext = this.getFileContext();
    const systemPrompt = fileContext
      ? `${this.systemPrompt}\n\n${fileContext}`
      : this.systemPrompt;

    return [
      { role: "system", content: systemPrompt },
      ...this.messages,
      { role: "user", content: userMessage },
    ];
  }

  /** Get file contents as context */
  private getFileContext(): string | null {
    if (this.files.size === 0) return null;

    const parts: string[] = ["Files in context:"];
    for (const filePath of this.files) {
      try {
        const content = fs.readFileSync(filePath, "utf-8");
        parts.push(`\n--- ${filePath} ---\n${content}`);
      } catch {
        parts.push(`\n--- ${filePath} --- (unreadable)`);
      }
    }
    return parts.join("\n");
  }

  /** Send a user message and get a response */
  async send(userMessage: string): Promise<string> {
    const allMessages = this.buildMessages(userMessage);

    const response = await sendMessage(this.config, allMessages, (chunk) => {
      process.stdout.write(chunk);
    });

    // Store in history
    this.messages.push({ role: "user", content: userMessage });
    this.messages.push({ role: "assistant", content: response });

    return response;
  }

  /** Clear chat history */
  clearHistory(): void {
    this.messages = [];
  }

  /** Create the command context for slash commands */
  createCommandContext(): CommandContext {
    return {
      config: this.config,
      messages: this.messages,
      files: this.files,
      setModel: (model: string) => {
        this.config = { ...this.config, model };
      },
      setSystemPrompt: (prompt: string) => {
        this.systemPrompt = prompt;
      },
      getSystemPrompt: () => this.systemPrompt,
      output: (text: string) => console.log(text),
      renderMarkdown: (text: string) => console.log(renderMarkdown(text)),
      listModels: () => fetchModels(this.config),
      getAgentsContent: () => this.agentsContent,
      clearHistory: () => this.clearHistory(),
      quit: () => {
        this.running = false;
      },
    };
  }

  /** Process a single input line (user message or command) */
  async processInput(input: string): Promise<void> {
    const parsed = parseCommand(input);
    if (parsed) {
      const [name, args] = parsed;
      const ctx = this.createCommandContext();
      const handled = await executeCommand(name, args, ctx);
      if (!handled) {
        console.log(formatError(`Unknown command: /${name}. Type /help for available commands.`));
      }
      return;
    }

    // Regular message
    try {
      process.stdout.write("\n");
      const response = await this.send(input);
      // After streaming, render full markdown version
      process.stdout.write("\n");
      console.log(renderMarkdown(response));
    } catch (err) {
      console.error(formatError(`Error: ${err instanceof Error ? err.message : String(err)}`));
    }
  }

  /** Start the interactive chat loop */
  async start(): Promise<void> {
    console.log(formatInfo(`node-aider started with model: ${this.config.model}`));
    console.log(formatInfo("Type /help for available commands.\n"));

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: true,
    });

    const askQuestion = (): void => {
      if (!this.running) {
        rl.close();
        return;
      }

      rl.question(formatPrompt(this.config.model), async (input) => {
        const trimmed = input.trim();
        if (trimmed) {
          await this.processInput(trimmed);
        }
        askQuestion();
      });
    };

    askQuestion();

    await new Promise<void>((resolve) => {
      rl.on("close", resolve);
    });

    console.log(formatInfo("Goodbye!"));
  }
}

/** Convenience function to list models */
export async function listModels(config: AiderConfig): Promise<ModelInfo[]> {
  return fetchModels(config);
}
