#!/usr/bin/env node
/** Entry point for node-aider */

import { buildConfig } from "./config.js";
import { ChatSession } from "./chat.js";

async function main(): Promise<void> {
  const config = buildConfig();

  if (!config.apiKey) {
    console.error(
      "Error: No API key configured. Set OPENAI_API_KEY env var, or use --api-key flag.",
    );
    process.exit(1);
  }

  const session = new ChatSession(config);
  await session.start();
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
