// Package render provides markdown rendering for terminal output.
package render

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/charmbracelet/glamour"
)

// Renderer renders markdown to the terminal.
type Renderer struct {
	gr     *glamour.TermRenderer
	writer io.Writer
}

// NewRenderer creates a Renderer writing to the given writer.
// If w is nil, os.Stdout is used.
func NewRenderer(w io.Writer) (*Renderer, error) {
	if w == nil {
		w = os.Stdout
	}
	gr, err := glamour.NewTermRenderer(
		glamour.WithAutoStyle(),
		glamour.WithWordWrap(100),
	)
	if err != nil {
		return nil, fmt.Errorf("create glamour renderer: %w", err)
	}
	return &Renderer{gr: gr, writer: w}, nil
}

// Render renders a complete markdown string to the writer.
func (r *Renderer) Render(markdown string) error {
	out, err := r.gr.Render(markdown)
	if err != nil {
		return fmt.Errorf("render markdown: %w", err)
	}
	_, err = fmt.Fprint(r.writer, out)
	return err
}

// RenderStream progressively renders streamed content.
// It accumulates deltas and renders when a complete block boundary is detected
// or when flush is true.
func (r *Renderer) RenderStream(accumulated string, delta string, flush bool) (string, error) {
	accumulated += delta
	if flush || strings.Contains(delta, "\n\n") || strings.HasSuffix(accumulated, "```\n") {
		if err := r.Render(accumulated); err != nil {
			return "", err
		}
		return "", nil // reset accumulator after rendering
	}
	return accumulated, nil
}
