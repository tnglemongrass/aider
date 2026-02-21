package prompts

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestMainSystemPrompt(t *testing.T) {
	p := MainSystemPrompt("English")
	assert.Contains(t, p, "expert software developer")
	assert.Contains(t, p, "English")
}

func TestMainSystemPromptLanguage(t *testing.T) {
	p := MainSystemPrompt("Spanish")
	assert.Contains(t, p, "Spanish")
}

func TestCommitMessagePrompt(t *testing.T) {
	assert.True(t, strings.Contains(CommitMessagePrompt, "conventional commit"))
	assert.Contains(t, CommitMessagePrompt, "imperative mood")
}
