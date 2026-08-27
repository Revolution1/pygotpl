package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html/template"
	"io"
	"os"
	texttemplate "text/template"

	"github.com/Masterminds/sprig/v3"
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
		if err := encoder.Encode(execute(req)); err != nil {
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
	if req.Engine == "html" {
		return executeHTML(req, data)
	}
	if req.Engine == "text" {
		return executeText(req, data)
	}
	return failed("input", fmt.Errorf("unsupported engine %q", req.Engine))
}

func executeText(req request, data any) response {
	functions, err := textFunctions(req.FunctionProfile)
	if err != nil {
		return failed("input", err)
	}
	tmpl := texttemplate.New(req.Name).Funcs(functions)
	if req.Delimiters != nil {
		tmpl = tmpl.Delims(req.Delimiters.Left, req.Delimiters.Right)
	}
	if len(req.Options) != 0 {
		tmpl = tmpl.Option(req.Options...)
	}
	parsed, parseErr := tmpl.Parse(req.Template)
	if parseErr != nil {
		return failed("parse", parseErr)
	}
	var buffer bytes.Buffer
	var executeErr error
	if req.ExecuteTemplate == "" {
		executeErr = parsed.Execute(&buffer, data)
	} else {
		executeErr = parsed.ExecuteTemplate(&buffer, req.ExecuteTemplate, data)
	}
	if executeErr != nil {
		return response{Output: buffer.String(), Error: errorValue("execute", executeErr)}
	}
	return response{Output: buffer.String()}
}

func executeHTML(req request, data any) response {
	functions, err := htmlFunctions(req.FunctionProfile)
	if err != nil {
		return failed("input", err)
	}
	tmpl := template.New(req.Name).Funcs(functions)
	if req.Delimiters != nil {
		tmpl = tmpl.Delims(req.Delimiters.Left, req.Delimiters.Right)
	}
	if len(req.Options) != 0 {
		tmpl = tmpl.Option(req.Options...)
	}
	parsed, parseErr := tmpl.Parse(req.Template)
	if parseErr != nil {
		return failed("parse", parseErr)
	}
	var buffer bytes.Buffer
	var executeErr error
	if req.ExecuteTemplate == "" {
		executeErr = parsed.Execute(&buffer, data)
	} else {
		executeErr = parsed.ExecuteTemplate(&buffer, req.ExecuteTemplate, data)
	}
	if executeErr != nil {
		return response{Output: buffer.String(), Error: errorValue("execute", executeErr)}
	}
	return response{Output: buffer.String()}
}

func textFunctions(profile string) (texttemplate.FuncMap, error) {
	switch profile {
	case "sprig":
		return sprig.TxtFuncMap(), nil
	case "sprig-hermetic":
		return sprig.HermeticTxtFuncMap(), nil
	default:
		return nil, fmt.Errorf("unsupported Sprig function profile %q", profile)
	}
}

func htmlFunctions(profile string) (template.FuncMap, error) {
	switch profile {
	case "sprig":
		return sprig.HtmlFuncMap(), nil
	case "sprig-hermetic":
		return sprig.HermeticHtmlFuncMap(), nil
	default:
		return nil, fmt.Errorf("unsupported Sprig function profile %q", profile)
	}
}

func failed(phase string, err error) response {
	return response{Error: errorValue(phase, err)}
}

func errorValue(phase string, err error) *oracleError {
	return &oracleError{Phase: phase, Message: err.Error()}
}
