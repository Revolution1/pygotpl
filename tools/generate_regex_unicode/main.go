// Command generate_regex_unicode writes the pinned Go Unicode range tables
// consumed by pygotpl's pure-Python RE2 compatibility layer.
package main

import (
	"bytes"
	"fmt"
	"os"
	"sort"
	"strconv"
	"unicode"
)

func main() {
	if len(os.Args) != 2 {
		fail(fmt.Errorf("usage: go run tools/generate_regex_unicode/main.go OUTPUT"))
	}
	var output bytes.Buffer
	output.WriteString("# Code generated from Go unicode tables; DO NOT EDIT.\n")
	output.WriteString("\nfrom typing import Final, TypeAlias\n\n")
	output.WriteString("Range: TypeAlias = tuple[int, int, int]\n\n")
	output.WriteString("UNICODE_VERSION: Final = ")
	output.WriteString(strconv.Quote(unicode.Version))
	output.WriteString("\n\n")
	output.WriteString("PROPERTY_RANGES: Final[dict[str, tuple[Range, ...]]] = {\n")
	tables := make(map[string]*unicode.RangeTable)
	for name, table := range unicode.Categories {
		tables[name] = table
	}
	for name, table := range unicode.Scripts {
		tables[name] = table
	}
	for _, name := range sortedKeys(tables) {
		if rangeCount(tables[name]) == 1 {
			fmt.Fprintf(&output, "    %q: (", name)
			writeRange(&output, tables[name])
			output.WriteString(",),\n")
			continue
		}
		fmt.Fprintf(&output, "    %q: (\n", name)
		writeRanges(&output, tables[name])
		output.WriteString("    ),\n")
	}
	output.WriteString("}\n\n")
	output.WriteString("CATEGORY_ALIASES: Final[dict[str, str]] = {\n")
	for _, name := range sortedKeys(unicode.CategoryAliases) {
		fmt.Fprintf(
			&output,
			"    %q: %q,\n",
			canonicalName(name),
			unicode.CategoryAliases[name],
		)
	}
	output.WriteString("}\n")

	if err := os.WriteFile(os.Args[1], output.Bytes(), 0o644); err != nil {
		fail(err)
	}
}

func writeRanges(output *bytes.Buffer, table *unicode.RangeTable) {
	for _, item := range table.R16 {
		fmt.Fprintf(
			output,
			"        (%d, %d, %d),\n",
			item.Lo,
			item.Hi,
			item.Stride,
		)
	}
	for _, item := range table.R32 {
		fmt.Fprintf(
			output,
			"        (%d, %d, %d),\n",
			item.Lo,
			item.Hi,
			item.Stride,
		)
	}
}

func rangeCount(table *unicode.RangeTable) int {
	return len(table.R16) + len(table.R32)
}

func writeRange(output *bytes.Buffer, table *unicode.RangeTable) {
	if len(table.R16) == 1 {
		item := table.R16[0]
		fmt.Fprintf(output, "(%d, %d, %d)", item.Lo, item.Hi, item.Stride)
		return
	}
	item := table.R32[0]
	fmt.Fprintf(output, "(%d, %d, %d)", item.Lo, item.Hi, item.Stride)
}

func sortedKeys[T any](values map[string]T) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func canonicalName(name string) string {
	result := make([]byte, 0, len(name))
	first := true
	for index := range len(name) {
		character := name[index]
		if character == '_' || character == '-' || character == ' ' {
			continue
		}
		if first {
			if 'a' <= character && character <= 'z' {
				character -= 'a' - 'A'
			}
			first = false
		} else if 'A' <= character && character <= 'Z' {
			character += 'a' - 'A'
		}
		result = append(result, character)
	}
	return string(result)
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(2)
}
