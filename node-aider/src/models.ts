/** Model management: fetch, cache, and switch models */

import type { AiderConfig, ModelInfo, ModelsResponse } from "./types.js";

let cachedModels: ModelInfo[] | null = null;

/** Fetch available models from the /v1/models endpoint */
export async function fetchModels(config: AiderConfig): Promise<ModelInfo[]> {
  if (cachedModels) return cachedModels;

  const url = `${config.apiBase}/models`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${config.apiKey}`,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to fetch models (${response.status}): ${text}`);
  }

  const data = (await response.json()) as ModelsResponse;
  cachedModels = data.data ?? [];
  return cachedModels;
}

/** Clear the cached model list */
export function clearModelCache(): void {
  cachedModels = null;
}

/** Check if a model name exists in the fetched model list */
export async function isValidModel(
  config: AiderConfig,
  modelName: string,
): Promise<boolean> {
  try {
    const models = await fetchModels(config);
    return models.some((m) => m.id === modelName);
  } catch {
    // If we can't fetch models, allow any model name
    return true;
  }
}

/** Format model list for display */
export function formatModelList(models: ModelInfo[], currentModel: string): string {
  if (models.length === 0) return "No models available.";

  const lines = models.map((m) => {
    const marker = m.id === currentModel ? " (current)" : "";
    return `  ${m.id}${marker}`;
  });

  return `Available models:\n${lines.join("\n")}`;
}
