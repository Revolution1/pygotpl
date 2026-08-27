package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"iter"
	"os"
	"strings"
	texttemplate "text/template"

	"github.com/Masterminds/sprig/v3"
	slimsprig "github.com/go-task/slim-sprig/v3"
)

type delimiters struct {
	Left  string `json:"left"`
	Right string `json:"right"`
}

type request struct {
	Engine          string          `json:"engine"`
	Name            string          `json:"name"`
	Template        string          `json:"template"`
	Data            json.RawMessage `json:"data"`
	Delimiters      *delimiters     `json:"delimiters,omitempty"`
	Options         []string        `json:"options,omitempty"`
	FunctionProfile string          `json:"function_profile,omitempty"`
	ExecuteTemplate string          `json:"execute_template,omitempty"`
}

type oracleError struct {
	Phase   string `json:"phase"`
	Message string `json:"message"`
}

type response struct {
	Output string       `json:"output"`
	Error  *oracleError `json:"error"`
}

func main() {
	if err := run(os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}

func run(input io.Reader, output io.Writer) error {
	decoder := json.NewDecoder(input)
	encoder := json.NewEncoder(output)
	for {
		var req request
		if err := decoder.Decode(&req); err != nil {
			if err == io.EOF {
				return nil
			}
			return fmt.Errorf("decode request: %w", err)
		}
		result := execute(req)
		if err := encoder.Encode(result); err != nil {
			return fmt.Errorf("encode response: %w", err)
		}
	}
}

func execute(req request) response {
	var data any
	if len(req.Data) != 0 && string(req.Data) != "null" {
		if err := json.Unmarshal(req.Data, &data); err != nil {
			return failed("input", err)
		}
	}

	switch req.Engine {
	case "text":
		return executeText(req, data)
	case "html":
		return executeHTML(req, data)
	default:
		return failed("input", fmt.Errorf("unsupported engine %q", req.Engine))
	}
}

func executeText(req request, data any) response {
	tmpl := texttemplate.New(req.Name)
	if funcs := textFunctions(req.FunctionProfile); funcs != nil {
		tmpl = tmpl.Funcs(funcs)
	}
	if req.Delimiters != nil {
		tmpl = tmpl.Delims(req.Delimiters.Left, req.Delimiters.Right)
	}
	if len(req.Options) != 0 {
		tmpl = tmpl.Option(req.Options...)
	}
	parsed, err := tmpl.Parse(req.Template)
	if err != nil {
		return failed("parse", err)
	}
	var buffer bytes.Buffer
	if req.ExecuteTemplate == "" {
		err = parsed.Execute(&buffer, data)
	} else {
		err = parsed.ExecuteTemplate(&buffer, req.ExecuteTemplate, data)
	}
	if err != nil {
		return response{Output: buffer.String(), Error: errorValue("execute", err)}
	}
	return response{Output: buffer.String()}
}

func executeHTML(req request, data any) response {
	tmpl := template.New(req.Name)
	if funcs := htmlFunctions(req.FunctionProfile); funcs != nil {
		tmpl = tmpl.Funcs(funcs)
	}
	if req.Delimiters != nil {
		tmpl = tmpl.Delims(req.Delimiters.Left, req.Delimiters.Right)
	}
	if len(req.Options) != 0 {
		tmpl = tmpl.Option(req.Options...)
	}
	parsed, err := tmpl.Parse(req.Template)
	if err != nil {
		return failed("parse", err)
	}
	var buffer bytes.Buffer
	if req.ExecuteTemplate == "" {
		err = parsed.Execute(&buffer, data)
	} else {
		err = parsed.ExecuteTemplate(&buffer, req.ExecuteTemplate, data)
	}
	if err != nil {
		return response{Output: buffer.String(), Error: errorValue("execute", err)}
	}
	return response{Output: buffer.String()}
}

func textFunctions(profile string) texttemplate.FuncMap {
	if funcs, ok := sproutFunctions(profile); ok {
		return funcs
	}
	switch profile {
	case "", "none":
		return nil
	case "sprig":
		return sprig.TxtFuncMap()
	case "sprig-hermetic":
		return sprig.HermeticTxtFuncMap()
	case "slim-sprig":
		return slimsprig.TxtFuncMap()
	case "slim-sprig-hermetic":
		return slimsprig.HermeticTxtFuncMap()
	case "parser-functions":
		return texttemplate.FuncMap{
			"break":    func(value any) any { return value },
			"continue": func(value any) any { return value },
			"custom":   func(value any) any { return value },
		}
	case "execution-functions":
		return texttemplate.FuncMap{
			"fail": func() (string, error) {
				return "", fmt.Errorf("oracle failure")
			},
			"join": func(left, right string) string { return left + "+" + right },
			"complexmap": func() map[complex128]string {
				return map[complex128]string{
					complex(2, -1): "two-minus-one",
					complex(-1, 3): "minus-one-three",
					complex(2, -2): "two-minus-two",
					complex(0, 4):  "zero-four",
				}
			},
			"bytes": func() []byte { return []byte("Go!\n") },
			"pointer": func() *int {
				value := 7
				return &value
			},
			"stringmap": func() map[string]string {
				return map[string]string{"present": "value"}
			},
			"intmap": func() map[string]int {
				return map[string]int{"present": 7}
			},
			"intkeymap": func() map[int]string {
				return map[int]string{10: "ten", 2: "two", 1: "one"}
			},
			"seq": func() iter.Seq[int] {
				return func(yield func(int) bool) {
					for value := range 2 {
						if !yield(value) {
							return
						}
					}
				}
			},
			"seq2": func() iter.Seq2[int, int] {
				return func(yield func(int, int) bool) {
					for key := range 2 {
						if !yield(key, key+10) {
							return
						}
					}
				}
			},
			"ok": func() (string, error) { return "ok", nil },
			"variadic": func(prefix string, values ...string) string {
				return prefix + ":" + strings.Join(values, ",")
			},
		}
	default:
		return texttemplate.FuncMap{
			"__invalid_profile": func() (string, error) {
				return "", fmt.Errorf("unsupported function profile %q", profile)
			},
		}
	}
}

func htmlFunctions(profile string) template.FuncMap {
	if funcs, ok := sproutFunctions(profile); ok {
		return template.FuncMap(funcs)
	}
	switch profile {
	case "", "none":
		return nil
	case "sprig":
		return sprig.HtmlFuncMap()
	case "sprig-hermetic":
		return sprig.HermeticHtmlFuncMap()
	case "slim-sprig":
		return slimsprig.HtmlFuncMap()
	case "slim-sprig-hermetic":
		return slimsprig.HermeticHtmlFuncMap()
	case "parser-functions":
		return template.FuncMap{
			"break":    func(value any) any { return value },
			"continue": func(value any) any { return value },
			"custom":   func(value any) any { return value },
		}
	case "trusted-content":
		return template.FuncMap{
			"trustedCSS":    func() template.CSS { return `a[href="//x"]{color:red}` },
			"trustedHTML":   func() template.HTML { return `Hello, <b>World</b> &amp;!` },
			"trustedAttr":   func() template.HTMLAttr { return ` dir="ltr"` },
			"trustedJS":     func() template.JS { return `x && alert("ok")` },
			"trustedJSStr":  func() template.JSStr { return `line\u0021` },
			"trustedURL":    func() template.URL { return `javascript:trusted()` },
			"trustedSrcset": func() template.Srcset { return `javascript:trusted() 2x, /safe 1x` },
		}
	case "execution-functions":
		return template.FuncMap{
			"fail": func() (string, error) {
				return "", fmt.Errorf("oracle failure")
			},
			"join": func(left, right string) string { return left + "+" + right },
			"complexmap": func() map[complex128]string {
				return map[complex128]string{
					complex(2, -1): "two-minus-one",
					complex(-1, 3): "minus-one-three",
					complex(2, -2): "two-minus-two",
					complex(0, 4):  "zero-four",
				}
			},
			"bytes": func() []byte { return []byte("Go!\n") },
			"pointer": func() *int {
				value := 7
				return &value
			},
			"stringmap": func() map[string]string {
				return map[string]string{"present": "value"}
			},
			"intmap": func() map[string]int {
				return map[string]int{"present": 7}
			},
			"intkeymap": func() map[int]string {
				return map[int]string{10: "ten", 2: "two", 1: "one"}
			},
			"seq": func() iter.Seq[int] {
				return func(yield func(int) bool) {
					for value := range 2 {
						if !yield(value) {
							return
						}
					}
				}
			},
			"seq2": func() iter.Seq2[int, int] {
				return func(yield func(int, int) bool) {
					for key := range 2 {
						if !yield(key, key+10) {
							return
						}
					}
				}
			},
			"ok": func() (string, error) { return "ok", nil },
			"variadic": func(prefix string, values ...string) string {
				return prefix + ":" + strings.Join(values, ",")
			},
		}
	default:
		return template.FuncMap{
			"__invalid_profile": func() (string, error) {
				return "", fmt.Errorf("unsupported function profile %q", profile)
			},
		}
	}
}

func failed(phase string, err error) response {
	return response{Error: errorValue(phase, err)}
}

func errorValue(phase string, err error) *oracleError {
	return &oracleError{Phase: phase, Message: err.Error()}
}
