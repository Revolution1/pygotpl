package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
)

type vector struct {
	Name   string `json:"name"`
	Format string `json:"format"`
	Output string `json:"output"`
}

func makeVector(name string, format string, values ...any) vector {
	return vector{name, format, fmt.Sprintf(format, values...)}
}

func main() {
	vectors := []vector{
		makeVector("plain-percent", "plain/%%"),
		makeVector("integer-flags", "%c|%.6U|%.4d|% d|%#x|%O|%-5d", 65, 65, 7, 7, 31, 8, -2),
		makeVector("width", "%5s|%05d", "x", 2),
		makeVector("float", "%+.1f|% .1f|%g", 2.0, 2.0, 12.193263113702178),
		makeVector("special-float", "%v|%v|%v", math.NaN(), math.Inf(1), math.Inf(-1)),
		makeVector("complex", "%g|%x", 1+2i, 1+2i),
		makeVector("string", "%s|%q|%x|%+q|%#q", "Go!", "Go!\n", "Go!", "café", "raw"),
		makeVector("unicode-precision", "%.3s|%.3q", "日本語abc", "日本語abc"),
		makeVector("bytes", "%s|%q|%x|%v|%#v|%T", []byte("Go!\n"), []byte("Go!\n"), []byte("Go!\n"), []byte{1, 15}, []byte{65}, []byte{}),
		makeVector("reordered", "%[2]d/%[1]d/%d", 11, 22, 33),
		makeVector("dynamic", "%[3]*.[2]*[1]f", 3.14159, 2, 8),
		makeVector("negative-width", "%*s", -5, "go"),
		makeVector("missing", "%s/%d", "only"),
		makeVector("bad-index", "%[3]d", 1),
		makeVector("bad-width", "%*d", "x", 1),
		makeVector("extra", "plain", 1),
		makeVector("nil", "%v|%T|%s", nil, nil, nil),
		makeVector("slice", "%v|%#v|%T", []any{"x", 1}, []any{"x", 1}, []any{}),
		makeVector("map", "%v", map[string]any{"b": 2, "a": 1}),
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(struct {
		Schema  int      `json:"schema"`
		Vectors []vector `json:"vectors"`
	}{1, vectors}); err != nil {
		panic(err)
	}
}
