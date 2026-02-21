import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AiderConfig, ModelsResponse } from "../src/types.js";
import { DEFAULT_CONFIG } from "../src/types.js";
import { fetchModels, clearModelCache, isValidModel, formatModelList } from "../src/models.js";

const mockConfig: AiderConfig = {
  ...DEFAULT_CONFIG,
  apiKey: "test-key",
  apiBase: "http://localhost:11434/v1",
};

function mockFetchResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    headers: new Headers(),
    text: async () => JSON.stringify(body),
    json: async () => body,
    body: null,
    redirected: false,
    type: "basic" as ResponseType,
    url: "",
    clone: () => mockFetchResponse(body, status),
    bodyUsed: false,
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
    bytes: async () => new Uint8Array(),
  } as Response;
}

describe("fetchModels", () => {
  beforeEach(() => {
    clearModelCache();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should fetch models from API", async () => {
    const modelsResponse: ModelsResponse = {
      object: "list",
      data: [
        { id: "gpt-4o", object: "model", owned_by: "openai" },
        { id: "gpt-4o-mini", object: "model", owned_by: "openai" },
      ],
    };

    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(modelsResponse));

    const models = await fetchModels(mockConfig);
    expect(models).toHaveLength(2);
    expect(models[0].id).toBe("gpt-4o");
    expect(models[1].id).toBe("gpt-4o-mini");
  });

  it("should cache model results", async () => {
    const modelsResponse: ModelsResponse = {
      object: "list",
      data: [{ id: "gpt-4o", object: "model" }],
    };

    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(modelsResponse));

    await fetchModels(mockConfig);
    await fetchModels(mockConfig);

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("should throw on API error", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockFetchResponse({ error: "unauthorized" }, 401),
    );

    await expect(fetchModels(mockConfig)).rejects.toThrow("Failed to fetch models");
  });

  it("should clear cache", async () => {
    const modelsResponse: ModelsResponse = {
      object: "list",
      data: [{ id: "gpt-4o", object: "model" }],
    };

    vi.mocked(fetch).mockResolvedValue(mockFetchResponse(modelsResponse));

    await fetchModels(mockConfig);
    clearModelCache();
    await fetchModels(mockConfig);

    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe("isValidModel", () => {
  beforeEach(() => {
    clearModelCache();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should return true for existing model", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockFetchResponse({
        object: "list",
        data: [{ id: "gpt-4o", object: "model" }],
      }),
    );

    expect(await isValidModel(mockConfig, "gpt-4o")).toBe(true);
  });

  it("should return false for non-existing model", async () => {
    vi.mocked(fetch).mockResolvedValue(
      mockFetchResponse({
        object: "list",
        data: [{ id: "gpt-4o", object: "model" }],
      }),
    );

    expect(await isValidModel(mockConfig, "nonexistent")).toBe(false);
  });

  it("should return true when API fetch fails (allow any model)", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("Network error"));

    expect(await isValidModel(mockConfig, "any-model")).toBe(true);
  });
});

describe("formatModelList", () => {
  it("should format empty list", () => {
    expect(formatModelList([], "gpt-4o")).toBe("No models available.");
  });

  it("should mark current model", () => {
    const models = [
      { id: "gpt-4o", object: "model" },
      { id: "gpt-4o-mini", object: "model" },
    ];
    const result = formatModelList(models, "gpt-4o");
    expect(result).toContain("gpt-4o (current)");
    expect(result).not.toContain("gpt-4o-mini (current)");
  });

  it("should list all models", () => {
    const models = [
      { id: "model-a", object: "model" },
      { id: "model-b", object: "model" },
      { id: "model-c", object: "model" },
    ];
    const result = formatModelList(models, "model-b");
    expect(result).toContain("model-a");
    expect(result).toContain("model-b (current)");
    expect(result).toContain("model-c");
  });
});
