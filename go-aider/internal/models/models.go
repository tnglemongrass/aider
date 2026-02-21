// Package models provides model listing and switching from an OpenAI-compatible API.
package models

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"

	"github.com/tnglemongrass/aider/go-aider/internal/llm"
)

// Manager fetches and caches the list of available models.
type Manager struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client

	mu     sync.Mutex
	cached []llm.ModelInfo
}

// NewManager creates a Manager for the given API endpoint.
func NewManager(baseURL, apiKey string) *Manager {
	return &Manager{
		baseURL:    strings.TrimRight(baseURL, "/"),
		apiKey:     apiKey,
		httpClient: http.DefaultClient,
	}
}

// List returns the available models, fetching from the API if not cached.
func (m *Manager) List() ([]llm.ModelInfo, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.cached != nil {
		return m.cached, nil
	}

	req, err := http.NewRequest(http.MethodGet, m.baseURL+"/v1/models", nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	if m.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+m.apiKey)
	}

	resp, err := m.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch models: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	var result llm.ModelListResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode models: %w", err)
	}

	m.cached = result.Data
	return m.cached, nil
}

// Invalidate clears the cached model list.
func (m *Manager) Invalidate() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.cached = nil
}

// Has returns true if the given model ID is in the list of available models.
func (m *Manager) Has(modelID string) (bool, error) {
	models, err := m.List()
	if err != nil {
		return false, err
	}
	for _, model := range models {
		if model.ID == modelID {
			return true, nil
		}
	}
	return false, nil
}
