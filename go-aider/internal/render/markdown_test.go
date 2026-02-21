package render

import (
	"bytes"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRender(t *testing.T) {
	var buf bytes.Buffer
	r, err := NewRenderer(&buf)
	require.NoError(t, err)

	err = r.Render("# Hello\n\nWorld")
	require.NoError(t, err)
	assert.Contains(t, buf.String(), "Hello")
	assert.Contains(t, buf.String(), "World")
}

func TestRenderStream(t *testing.T) {
	var buf bytes.Buffer
	r, err := NewRenderer(&buf)
	require.NoError(t, err)

	// Accumulate without rendering.
	acc, err := r.RenderStream("", "Hello ", false)
	require.NoError(t, err)
	assert.Equal(t, "Hello ", acc)
	assert.Empty(t, buf.String())

	// Flush renders and resets accumulator.
	acc, err = r.RenderStream(acc, "World", true)
	require.NoError(t, err)
	assert.Empty(t, acc)
	assert.Contains(t, buf.String(), "Hello")
}

func TestNewRendererNilWriter(t *testing.T) {
	// Should not panic; defaults to os.Stdout.
	r, err := NewRenderer(nil)
	require.NoError(t, err)
	assert.NotNil(t, r)
}
