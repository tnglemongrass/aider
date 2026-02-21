package config

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()
	assert.Equal(t, "gpt-4o", cfg.Model)
	assert.Equal(t, "https://api.openai.com", cfg.APIBase)
	assert.Equal(t, 4096, cfg.MaxTokens)
	assert.Equal(t, true, cfg.Stream)
}

func TestLoadFromCLIArgs(t *testing.T) {
	args := []string{"--model", "claude-3", "--api-key", "sk-test", "--max-tokens", "2048"}
	cfg, err := Load(args)
	require.NoError(t, err)
	assert.Equal(t, "claude-3", cfg.Model)
	assert.Equal(t, "sk-test", cfg.APIKey)
	assert.Equal(t, 2048, cfg.MaxTokens)
}

func TestLoadFromEnv(t *testing.T) {
	t.Setenv("AIDER_MODEL", "env-model")
	t.Setenv("OPENAI_API_KEY", "env-key")
	cfg, err := Load(nil)
	require.NoError(t, err)
	assert.Equal(t, "env-model", cfg.Model)
	assert.Equal(t, "env-key", cfg.APIKey)
}

func TestCLIOverridesEnv(t *testing.T) {
	t.Setenv("AIDER_MODEL", "env-model")
	cfg, err := Load([]string{"--model", "cli-model"})
	require.NoError(t, err)
	assert.Equal(t, "cli-model", cfg.Model)
}

func TestLoadYAML(t *testing.T) {
	dir := t.TempDir()
	yamlContent := []byte("model: yaml-model\napi-key: yaml-key\n")
	path := filepath.Join(dir, "config.yml")
	require.NoError(t, os.WriteFile(path, yamlContent, 0644))

	cfg := DefaultConfig()
	require.NoError(t, cfg.loadYAML(path))
	assert.Equal(t, "yaml-model", cfg.Model)
	assert.Equal(t, "yaml-key", cfg.APIKey)
}

func TestLoadYAMLMissing(t *testing.T) {
	cfg := DefaultConfig()
	err := cfg.loadYAML("/nonexistent/path.yml")
	assert.Error(t, err)
}
