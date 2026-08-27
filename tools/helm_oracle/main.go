package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	texttemplate "text/template"

	"helm.sh/helm/v4/pkg/chart/common"
	chart "helm.sh/helm/v4/pkg/chart/v2"
	"helm.sh/helm/v4/pkg/engine"
)

type request struct {
	Name          string            `json:"name"`
	Version       string            `json:"version"`
	AppVersion    string            `json:"app_version"`
	Templates     map[string]string `json:"templates"`
	Files         map[string]string `json:"files"`
	Dependencies  []request         `json:"dependencies"`
	Values        map[string]any    `json:"values"`
	ReleaseName   string            `json:"release_name"`
	Namespace     string            `json:"namespace"`
	Strict        bool              `json:"strict"`
	LintMode      bool              `json:"lint_mode"`
	CustomProfile string            `json:"custom_profile"`
}

type response struct {
	Output map[string]string `json:"output"`
	Error  string            `json:"error,omitempty"`
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
			return err
		}
		if err := encoder.Encode(execute(req)); err != nil {
			return err
		}
	}
}

func execute(req request) response {
	chrt := chartFromRequest(req)
	values := common.Values{
		"Values": req.Values,
		"Release": common.Values{
			"Name":      req.ReleaseName,
			"Namespace": req.Namespace,
			"IsUpgrade": false,
			"IsInstall": true,
			"Revision":  1,
			"Service":   "Helm",
		},
		"Capabilities": common.DefaultCapabilities,
	}
	renderer := engine.Engine{Strict: req.Strict, LintMode: req.LintMode}
	switch req.CustomProfile {
	case "":
	case "override-upper":
		renderer.CustomTemplateFuncs = texttemplate.FuncMap{
			"upper": func(value string) string { return "custom:" + value },
		}
	default:
		return response{Error: "unknown custom profile: " + req.CustomProfile}
	}
	rendered, err := renderer.Render(chrt, values)
	if err != nil {
		return response{Output: rendered, Error: err.Error()}
	}
	return response{Output: rendered}
}

func chartFromRequest(req request) *chart.Chart {
	templates := make([]*common.File, 0, len(req.Templates))
	for name, source := range req.Templates {
		templates = append(templates, &common.File{Name: name, Data: []byte(source)})
	}
	files := make([]*common.File, 0, len(req.Files))
	for name, source := range req.Files {
		files = append(files, &common.File{Name: name, Data: []byte(source)})
	}
	chrt := &chart.Chart{
		Metadata: &chart.Metadata{
			Name:       req.Name,
			Version:    req.Version,
			APIVersion: chart.APIVersionV2,
			AppVersion: req.AppVersion,
		},
		Templates: templates,
		Files:     files,
	}
	dependencies := make([]*chart.Chart, 0, len(req.Dependencies))
	for _, dependency := range req.Dependencies {
		dependencies = append(dependencies, chartFromRequest(dependency))
	}
	chrt.SetDependencies(dependencies...)
	return chrt
}
