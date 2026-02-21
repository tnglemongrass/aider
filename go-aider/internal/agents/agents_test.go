package agents

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoadFrom(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "AGENTS.md")
	require.NoError(t, os.WriteFile(path, []byte("# My Agent\nDo things well."), 0644))

	a, err := LoadFrom(path)
	require.NoError(t, err)
	assert.Contains(t, a.Content, "My Agent")
	assert.Equal(t, []string{path}, a.Sources)
}

func TestLoadFromMissing(t *testing.T) {
	_, err := LoadFrom("/nonexistent/AGENTS.md")
	assert.Error(t, err)
}

func TestSystemContext(t *testing.T) {
	a := &Agents{Content: "Be helpful."}
	ctx := a.SystemContext()
	assert.Contains(t, ctx, "AGENTS.md")
	assert.Contains(t, ctx, "Be helpful.")
}

func TestSystemContextEmpty(t *testing.T) {
	a := &Agents{}
	assert.Empty(t, a.SystemContext())
}

func TestHasContent(t *testing.T) {
	assert.False(t, (&Agents{}).HasContent())
	assert.True(t, (&Agents{Content: "x"}).HasContent())
}

func TestTryLoad(t *testing.T) {
	dir := t.TempDir()
	f1 := filepath.Join(dir, "a.md")
	f2 := filepath.Join(dir, "b.md")
	require.NoError(t, os.WriteFile(f1, []byte("First"), 0644))
	require.NoError(t, os.WriteFile(f2, []byte("Second"), 0644))

	a := &Agents{}
	a.tryLoad(f1)
	a.tryLoad(f2)
	assert.Contains(t, a.Content, "First")
	assert.Contains(t, a.Content, "Second")
	assert.Contains(t, a.Content, "---")
	assert.Len(t, a.Sources, 2)
}

func TestLoadSkills(t *testing.T) {
	dir := t.TempDir()
	skillsDir := filepath.Join(dir, "skills")
	require.NoError(t, os.MkdirAll(skillsDir, 0755))
	require.NoError(t, os.WriteFile(filepath.Join(skillsDir, "go.md"), []byte("Go skills"), 0644))
	require.NoError(t, os.WriteFile(filepath.Join(skillsDir, "not.txt"), []byte("Ignored"), 0644))

	a := &Agents{}
	a.loadSkills(skillsDir)
	assert.Contains(t, a.Content, "Go skills")
	assert.NotContains(t, a.Content, "Ignored")
}
