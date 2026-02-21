/** Core type definitions for node-aider */

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface AiderConfig {
  model: string;
  apiKey: string;
  apiBase: string;
  maxTokens: number;
  temperature: number;
  stream: boolean;
  editFormat: string;
  configPath?: string;
  language: string;
}

export interface ModelInfo {
  id: string;
  object: string;
  created?: number;
  owned_by?: string;
}

export interface ModelsResponse {
  data: ModelInfo[];
  object: string;
}

export interface StreamChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: StreamChoice[];
}

export interface StreamChoice {
  index: number;
  delta: {
    role?: string;
    content?: string;
  };
  finish_reason: string | null;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface Command {
  name: string;
  description: string;
  usage: string;
  execute: (args: string, context: CommandContext) => Promise<void> | void;
}

export interface CommandContext {
  config: AiderConfig;
  messages: ChatMessage[];
  files: Set<string>;
  setModel: (model: string) => void;
  setSystemPrompt: (prompt: string) => void;
  getSystemPrompt: () => string;
  output: (text: string) => void;
  renderMarkdown: (text: string) => void;
  listModels: () => Promise<ModelInfo[]>;
  getAgentsContent: () => string | null;
  clearHistory: () => void;
  quit: () => void;
}

export const DEFAULT_CONFIG: AiderConfig = {
  model: "gpt-4o",
  apiKey: "",
  apiBase: "https://api.openai.com/v1",
  maxTokens: 4096,
  temperature: 0.7,
  stream: true,
  editFormat: "diff",
  language: "English",
};
