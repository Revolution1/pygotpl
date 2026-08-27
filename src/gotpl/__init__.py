"""Go template compatibility for Python."""

from .errors import (
    AsyncRequiredError,
    BudgetExceededError,
    SandboxViolationError,
    TemplateError,
    TemplateExecutionError,
    TemplateSyntaxError,
)
from .html import (
    CSS,
    HTML,
    JS,
    URL,
    HTMLAttr,
    HTMLTemplate,
    JSStr,
    Srcset,
    render_html,
    render_html_async,
    render_html_async_to,
    render_html_to,
)
from .pythonic import PythonExtensions
from .runtime import (
    AsyncTextWriter,
    ExecutionBudget,
    FormatMode,
    FunctionResult,
    GoFormatSpec,
    GoFormatter,
    GoPointer,
    GoSeq,
    GoSeq2,
    MissingKeyMode,
    SandboxPolicy,
    TypedMap,
)
from .runtime.engine import TemplateEngine
from .template import Template, render, render_async, render_async_to, render_to

__all__ = [
    "CSS",
    "HTML",
    "JS",
    "URL",
    "AsyncRequiredError",
    "AsyncTextWriter",
    "BudgetExceededError",
    "ExecutionBudget",
    "FormatMode",
    "FunctionResult",
    "GoFormatSpec",
    "GoFormatter",
    "GoPointer",
    "GoSeq",
    "GoSeq2",
    "HTMLAttr",
    "HTMLTemplate",
    "JSStr",
    "MissingKeyMode",
    "PythonExtensions",
    "SandboxPolicy",
    "SandboxViolationError",
    "Srcset",
    "Template",
    "TemplateEngine",
    "TemplateError",
    "TemplateExecutionError",
    "TemplateSyntaxError",
    "TypedMap",
    "__version__",
    "render",
    "render_async",
    "render_async_to",
    "render_html",
    "render_html_async",
    "render_html_async_to",
    "render_html_to",
    "render_to",
]

__version__ = "0.0.0"
