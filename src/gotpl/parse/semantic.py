"""Go-compatible semantic validation for parsed template trees."""

from collections.abc import Collection

from gotpl.errors import TemplateSyntaxError

from .nodes import (
    ActionNode,
    BlockNode,
    IdentifierNode,
    IfNode,
    ListNode,
    ParenthesizedNode,
    ParsedTemplate,
    PipeNode,
    RangeNode,
    TemplateCallNode,
    TermNode,
    VariableNode,
    WithNode,
)

BUILTIN_FUNCTIONS = frozenset(
    {
        "and",
        "call",
        "eq",
        "ge",
        "gt",
        "html",
        "index",
        "js",
        "le",
        "len",
        "lt",
        "ne",
        "not",
        "or",
        "print",
        "printf",
        "println",
        "slice",
        "urlquery",
    }
)


def validate_template(
    source: str,
    template: ParsedTemplate,
    *,
    functions: Collection[str] = (),
) -> None:
    """Validate scopes and declaration contexts after syntactic parsing."""

    validator = _SemanticValidator(source, BUILTIN_FUNCTIONS | set(functions))
    validator.validate_list(template.root, {"$"})
    for definition in template.definitions:
        validator.validate_list(definition.body, {"$"})


class _SemanticValidator:
    def __init__(self, source: str, functions: set[str] | frozenset[str]) -> None:
        self.source = source
        self.functions = functions

    def validate_list(self, root: ListNode, scope: set[str]) -> None:
        for node in root.nodes:
            if isinstance(node, ActionNode):
                self.validate_pipeline(node.pipeline, scope, max_declarations=1)
            elif isinstance(node, IfNode | WithNode):
                self.validate_branch(node, scope)
            elif isinstance(node, RangeNode):
                self.validate_range(node, scope)
            elif (
                isinstance(node, TemplateCallNode | BlockNode)
                and node.pipeline is not None
            ):
                self.validate_pipeline(
                    node.pipeline,
                    scope,
                    max_declarations=0,
                    declarations_allowed=False,
                )

    def validate_branch(self, node: IfNode | WithNode, scope: set[str]) -> None:
        branch_scope = scope.copy()
        self.validate_pipeline(node.pipeline, branch_scope, max_declarations=1)
        control_scope = branch_scope.copy()
        self.validate_list(node.body, control_scope)
        if node.else_body is not None:
            self.validate_list(node.else_body, control_scope)

    def validate_range(self, node: RangeNode, scope: set[str]) -> None:
        branch_scope = scope.copy()
        self.validate_pipeline(node.pipeline, branch_scope, max_declarations=2)
        control_scope = branch_scope.copy()
        self.validate_list(node.body, control_scope)
        if node.else_body is not None:
            self.validate_list(node.else_body, control_scope)

    def validate_pipeline(
        self,
        pipeline: PipeNode,
        scope: set[str],
        *,
        max_declarations: int,
        declarations_allowed: bool = True,
    ) -> None:
        for command in pipeline.commands:
            for term in command.arguments:
                self.validate_term(term, scope)

        declarations = pipeline.declarations
        if declarations and not declarations_allowed:
            raise self.error(
                declarations[0], "declaration not allowed in this pipeline"
            )
        if len(declarations) > max_declarations:
            raise self.error(
                declarations[max_declarations], "too many declarations in command"
            )
        if pipeline.is_assignment:
            for variable in declarations:
                self.require_defined(variable, scope)
        else:
            scope.update(variable.name for variable in declarations)

    def validate_term(self, term: TermNode, scope: set[str]) -> None:
        if isinstance(term, VariableNode):
            self.require_defined(term, scope)
        elif isinstance(term, IdentifierNode):
            if term.name not in self.functions:
                raise self.error(term, f"function {term.name!r} not defined")
        elif isinstance(term, ParenthesizedNode):
            self.validate_pipeline(
                term.pipeline,
                scope.copy(),
                max_declarations=0,
                declarations_allowed=False,
            )

    def require_defined(self, variable: VariableNode, scope: set[str]) -> None:
        if variable.name not in scope:
            raise self.error(variable, f"undefined variable {variable.name!r}")

    def error(self, node: TermNode, message: str) -> TemplateSyntaxError:
        encoded = self.source.encode("utf-8")
        line = encoded.count(b"\n", 0, node.start) + 1
        line_start = encoded.rfind(b"\n", 0, node.start) + 1
        return TemplateSyntaxError(
            message,
            position=node.start,
            line=line,
            column=node.start - line_start + 1,
        )
