// Package agents loads and manages AGENTS.md files for additional system context.
package agents

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Agents holds loaded agent context content.
type Agents struct {
	Content string
	Sources []string
}

// Load reads AGENTS.md files from standard locations and returns combined content.
// Search order:
//  1. .github/AGENTS.md (repo)
//  2. AGENTS.md (repo root)
//  3. ~/.aider/AGENTS.md (global)
//  4. .aider/skills/*.md (skills directory)
func Load() *Agents {
	a := &Agents{}
	// Repo-level paths.
	repoPaths := []string{
		filepath.Join(".github", "AGENTS.md"),
		"AGENTS.md",
	}
	for _, p := range repoPaths {
		a.tryLoad(p)
	}

	// Global path.
	if home, err := os.UserHomeDir(); err == nil {
		a.tryLoad(filepath.Join(home, ".aider", "AGENTS.md"))
	}

	// Skills directory.
	a.loadSkills(".aider/skills")

	return a
}

// LoadFrom reads AGENTS.md from a specific path.
func LoadFrom(path string) (*Agents, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read agents file: %w", err)
	}
	return &Agents{Content: string(data), Sources: []string{path}}, nil
}

func (a *Agents) tryLoad(path string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	if a.Content != "" {
		a.Content += "\n\n---\n\n"
	}
	a.Content += string(data)
	a.Sources = append(a.Sources, path)
}

func (a *Agents) loadSkills(dir string) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".md") {
			continue
		}
		a.tryLoad(filepath.Join(dir, e.Name()))
	}
}

// SystemContext returns the combined content suitable for system prompt injection.
// Returns empty string if no content was loaded.
func (a *Agents) SystemContext() string {
	if a.Content == "" {
		return ""
	}
	return fmt.Sprintf("Additional project context from AGENTS.md:\n\n%s", a.Content)
}

// HasContent reports whether any AGENTS.md content was loaded.
func (a *Agents) HasContent() bool {
	return a.Content != ""
}
