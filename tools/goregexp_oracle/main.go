package main

import (
	"encoding/json"
	"os"
	"regexp"
)

type vector struct {
	Name   string `json:"name"`
	Output any    `json:"output"`
}

func must(pattern string) *regexp.Regexp {
	return regexp.MustCompile(pattern)
}

func main() {
	vectors := []vector{
		{"ascii-digit", must(`^\d+$`).MatchString("١")},
		{"leftmost-first", must(`a|aa`).FindString("aa")},
		{"find-all-empty", must(`a*`).FindAllString("baaab", -1)},
		{"find-all-zero", must(`a`).FindAllString("banana", 0)},
		{"named-replacement", string(must(`(?P<word>[a-z]+)`).ReplaceAll([]byte("abc-12"), []byte(`<${word}>`)))},
		{"literal-replacement", string(must(`a`).ReplaceAllLiteral([]byte("banana"), []byte(`$1`)))},
		{"split-capture", must(`(a)`).Split("banana", -1)},
		{"split-one", must(`a`).Split("banana", 1)},
		{"quote-meta", regexp.QuoteMeta(`a+b[0]`)},
		{"unicode-greek", must(`^\p{Greek}+$`).MatchString("Ωβ")},
		{"unicode-complement", must(`^\P{ASCII}+$`).MatchString("é")},
		{"ungreedy", must(`(?U)a.+b`).FindString("a1b2b")},
		{"octal", must(`\777`).MatchString("ǿ")},
		{"empty-split", must("").Split("éx", -1)},
	}
	result := struct {
		Schema  int      `json:"schema"`
		Vectors []vector `json:"vectors"`
	}{1, vectors}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		panic(err)
	}
}
