// Package config provides configuration management with CLI > env > file precedence.
package config

import (
	"os"
	"path/filepath"

	"github.com/joho/godotenv"
	flag "github.com/spf13/pflag"
	"gopkg.in/yaml.v3"
)

// Config holds all configuration options for go-aider.
type Config struct {
	Model       string  `yaml:"model"`
	APIKey      string  `yaml:"api-key"`
	APIBase     string  `yaml:"api-base"`
	MaxTokens   int     `yaml:"max-tokens"`
	Temperature float64 `yaml:"temperature"`
	Stream      bool    `yaml:"stream"`
	EditFormat  string  `yaml:"edit-format"`
	Language    string  `yaml:"language"`
}

// DefaultConfig returns a Config with sensible defaults.
func DefaultConfig() *Config {
	return &Config{
		Model:       "gpt-4o",
		APIBase:     "https://api.openai.com",
		MaxTokens:   4096,
		Temperature: 0.7,
		Stream:      true,
		EditFormat:  "diff",
		Language:    "English",
	}
}

// Load builds a Config by merging CLI flags, environment variables, and config files.
// Precedence: CLI args > env vars > config files (cwd then $HOME).
func Load(args []string) (*Config, error) {
	cfg := DefaultConfig()

	// Load config files (lowest precedence first, then overwrite).
	if home, err := os.UserHomeDir(); err == nil {
		_ = cfg.loadYAML(filepath.Join(home, ".aider.conf.yml"))
	}
	_ = cfg.loadYAML(".aider.conf.yml")

	// Load .env files.
	_ = godotenv.Load()

	// Apply env vars.
	cfg.applyEnv()

	// Parse CLI flags (highest precedence).
	if err := cfg.parseFlags(args); err != nil {
		return nil, err
	}

	return cfg, nil
}

func (c *Config) loadYAML(path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return yaml.Unmarshal(data, c)
}

func (c *Config) applyEnv() {
	if v := os.Getenv("AIDER_MODEL"); v != "" {
		c.Model = v
	}
	if v := os.Getenv("OPENAI_API_KEY"); v != "" {
		c.APIKey = v
	}
	if v := os.Getenv("OPENAI_API_BASE"); v != "" {
		c.APIBase = v
	}
	if v := os.Getenv("AIDER_LANGUAGE"); v != "" {
		c.Language = v
	}
}

func (c *Config) parseFlags(args []string) error {
	fs := flag.NewFlagSet("aider", flag.ContinueOnError)
	fs.StringVar(&c.Model, "model", c.Model, "Model name to use")
	fs.StringVar(&c.APIKey, "api-key", c.APIKey, "API key")
	fs.StringVar(&c.APIBase, "api-base", c.APIBase, "API base URL")
	fs.IntVar(&c.MaxTokens, "max-tokens", c.MaxTokens, "Maximum tokens")
	fs.Float64Var(&c.Temperature, "temperature", c.Temperature, "Sampling temperature")
	fs.BoolVar(&c.Stream, "stream", c.Stream, "Enable streaming")
	fs.StringVar(&c.EditFormat, "edit-format", c.EditFormat, "Edit format (diff, whole)")
	fs.StringVar(&c.Language, "language", c.Language, "Reply language")
	return fs.Parse(args)
}
