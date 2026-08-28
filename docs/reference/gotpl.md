# gotpl API

The package root is the supported import surface for rendering, reusable
templates, policies, errors, and compatibility value adapters.

Start with the task-oriented [API overview](../api.md). Use
[Reusable Templates and Environments](../reusable-templates.md) for
construction and association choices, [Runtime Extensions](../extensions.md)
for context-aware integration APIs, and the [async](../async.md),
[HTML](../html.md), and [sandbox](../sandbox.md) guides for their respective
runtime behavior. This page owns complete generated signatures, not tutorials.

::: gotpl
    options:
      members:
        - __version__
        - render
        - render_to
        - render_async
        - render_async_to
        - render_html
        - render_html_to
        - render_html_async
        - render_html_async_to
        - Template
        - HTMLTemplate
        - TemplateEngine
        - Environment
        - ContextFunction
        - RenderContext
        - AsyncRenderContext
        - Extension
        - ExecutionBudget
        - SandboxPolicy
        - PythonExtensions
        - AsyncTextWriter
        - FormatMode
        - MissingKeyMode
        - TypedMap
        - GoSeq
        - GoSeq2
        - GoPointer
        - FunctionResult
        - GoFormatSpec
        - GoFormatter
        - TemplateError
        - TemplateSyntaxError
        - TemplateExecutionError
        - AsyncRequiredError
        - SandboxViolationError
        - BudgetExceededError
        - HTML
        - CSS
        - HTMLAttr
        - JS
        - JSStr
        - URL
        - Srcset
