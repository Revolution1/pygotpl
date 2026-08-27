"""Public exception hierarchy for gotpl."""


class TemplateError(Exception):
    """Base class for template errors."""


class TemplateSyntaxError(TemplateError):
    """Raised when template source cannot be parsed."""

    position: int
    line: int
    column: int

    def __init__(
        self,
        message: str,
        *,
        position: int,
        line: int = 1,
        column: int | None = None,
    ) -> None:
        self.position = position
        self.line = line
        self.column = position + 1 if column is None else column
        super().__init__(f"template:{self.line}:{self.column}: {message}")


class TemplateExecutionError(TemplateError):
    """Raised when a valid template cannot be executed."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.position: int | None = None
        self.line: int | None = None
        self.column: int | None = None
        self.source_name: str | None = None
        self.template_name: str | None = None
        super().__init__(message)

    def attach_location(
        self,
        source: str,
        position: int,
        *,
        source_name: str,
        template_name: str,
    ) -> None:
        """Attach the innermost execution location once."""

        if self.position is not None:
            return
        source_bytes = source.encode()
        bounded_position = min(max(position, 0), len(source_bytes))
        prefix = source_bytes[:bounded_position].decode(errors="replace")
        self.position = bounded_position
        self.line = prefix.count("\n") + 1
        self.column = len(prefix.rsplit("\n", 1)[-1]) + 1
        self.source_name = source_name
        self.template_name = template_name
        TemplateError.__init__(
            self,
            f"template: {source_name}:{self.line}:{self.column}: "
            f'executing "{template_name}": {self.message}',
        )


class AsyncRequiredError(TemplateExecutionError):
    """Raised when synchronous rendering encounters an awaitable value."""


class SandboxViolationError(TemplateExecutionError):
    """Raised when an opt-in sandbox denies a template capability."""


class BudgetExceededError(TemplateExecutionError):
    """Raised when an opt-in execution budget is exhausted."""
