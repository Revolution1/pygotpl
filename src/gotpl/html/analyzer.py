"""Rewrite output instructions with context-specific Go HTML escapers."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from hashlib import blake2s
from typing import TypeAlias

from gotpl.compile import (
    BranchTarget,
    CallTarget,
    CompiledCommand,
    CompiledPipeline,
    Instruction,
    OpCode,
    Operand,
    OperandKind,
    Program,
    RangeNextTarget,
    RangeTarget,
)
from gotpl.errors import TemplateSyntaxError

from .context import AttributeKind, Context, ContextKind, EscapeKind, JSContext, URLPart

_ContextKey: TypeAlias = tuple[object, ...]
_VariantKey: TypeAlias = tuple[str, _ContextKey]
_CallResolver: TypeAlias = Callable[[str, Context], tuple[str, Context]]

_ESCAPER_NAMES = {
    EscapeKind.HTML: "_html_template_htmlescaper",
    EscapeKind.RCDATA: "_html_template_rcdataescaper",
    EscapeKind.ATTR: "_html_template_attrescaper",
    EscapeKind.NOSPACE: "_html_template_nospaceescaper",
    EscapeKind.COMMENT: "_html_template_commentescaper",
    EscapeKind.URL_FILTER: "_html_template_urlfilter",
    EscapeKind.URL_NORMALIZER: "_html_template_urlnormalizer",
    EscapeKind.URL_ESCAPER: "_html_template_urlescaper",
    EscapeKind.JS_VALUE: "_html_template_jsvalescaper",
    EscapeKind.JS_STRING: "_html_template_jsstrescaper",
    EscapeKind.JS_TEMPLATE: "_html_template_jstmpllitescaper",
    EscapeKind.JS_REGEXP: "_html_template_jsregexpescaper",
    EscapeKind.CSS_VALUE: "_html_template_cssvaluefilter",
    EscapeKind.CSS_STRING: "_html_template_cssescaper",
    EscapeKind.SRCSET: "_html_template_srcsetescaper",
    EscapeKind.HTML_NAME: "_html_template_htmlnamefilter",
}
_PREDEFINED_ESCAPERS = frozenset({"html", "urlquery"})
_EQUIVALENT_ESCAPERS = {
    "_html_template_attrescaper": "html",
    "_html_template_htmlescaper": "html",
    "_html_template_rcdataescaper": "html",
    "_html_template_urlescaper": "urlquery",
    "_html_template_urlnormalizer": "urlquery",
}
_REDUNDANT_ESCAPERS = {
    "_html_template_commentescaper": frozenset(
        {"_html_template_attrescaper", "_html_template_htmlescaper"}
    ),
    "_html_template_cssescaper": frozenset({"_html_template_attrescaper"}),
    "_html_template_jsregexpescaper": frozenset({"_html_template_attrescaper"}),
    "_html_template_jsstrescaper": frozenset({"_html_template_attrescaper"}),
    "_html_template_jstmpllitescaper": frozenset({"_html_template_attrescaper"}),
    "_html_template_urlescaper": frozenset({"_html_template_urlnormalizer"}),
}


def analyze_program_with_text_roots(
    program: Program,
) -> tuple[Program, frozenset[str]]:
    """Return the rewritten set and names safe to execute from text context."""

    analyzer = _Analyzer(program)
    rewritten = analyzer.analyze()
    return rewritten, analyzer.text_root_names()


@dataclass(slots=True)
class _Variant:
    source: Program
    start: Context
    name: str
    output: Context
    program: Program | None = None


class _Analyzer:
    """Compute context-specialized template variants to a fixed point."""

    def __init__(self, root: Program) -> None:
        self.root = root
        self.sources = {item.name: item for item in root.definitions}
        self.sources[root.name] = root
        self.variants: dict[_VariantKey, _Variant] = {}

    def analyze(self) -> Program:
        default = Context()
        root_key = self._ensure_variant(self.root.name, default)
        for definition in self.root.definitions:
            self._ensure_variant(definition.name, default)

        for _round in range(256):
            changed = False
            for _key, variant in tuple(self.variants.items()):
                rewritten, output = _rewrite_program(
                    variant.source,
                    variant.start,
                    resolve=self._resolve_call,
                    name=variant.name,
                )
                if variant.program != rewritten or variant.output != output:
                    variant.program = rewritten
                    variant.output = output
                    changed = True
            if not changed:
                break
        else:  # pragma: no cover - finite contexts should always stabilize
            raise TemplateSyntaxError(
                "recursive templates do not converge to a stable HTML context",
                position=0,
            )

        root_variant = self.variants[root_key]
        assert root_variant.program is not None
        if root_variant.output.kind is not ContextKind.TEXT:
            raise TemplateSyntaxError(
                "template ends in a non-text context",
                position=len(root_variant.source.source),
            )
        definitions: list[Program] = []
        for key, variant in self.variants.items():
            if key == root_key:
                continue
            assert variant.program is not None
            definitions.append(variant.program)
        return replace(root_variant.program, definitions=tuple(definitions))

    def _resolve_call(self, name: str, context: Context) -> tuple[str, Context]:
        if name not in self.sources:
            return name, replace(context)
        key = self._ensure_variant(name, context)
        variant = self.variants[key]
        return variant.name, replace(variant.output)

    def text_root_names(self) -> frozenset[str]:
        default_key = _context_key(Context())
        return frozenset(
            name
            for name in self.sources
            if self.variants[(name, default_key)].output.kind is ContextKind.TEXT
        )

    def _ensure_variant(self, name: str, context: Context) -> _VariantKey:
        key = (name, _context_key(context))
        if key not in self.variants:
            start = replace(context)
            self.variants[key] = _Variant(
                source=self.sources[name],
                start=start,
                name=name if start == Context() else _variant_name(name, start),
                output=replace(start),
            )
        return key


def _rewrite_program(
    program: Program,
    start: Context,
    *,
    resolve: _CallResolver,
    name: str,
) -> tuple[Program, Context]:
    call_names: dict[int, str] = {}
    contexts, output = _propagate_contexts(
        program,
        start,
        resolve=resolve,
        call_names=call_names,
    )
    instructions: list[Instruction] = []
    for index, instruction in enumerate(program.instructions):
        context = replace(contexts.get(index, start))
        if instruction.opcode is OpCode.WRITE_TEXT:
            argument = instruction.argument
            assert isinstance(argument, str)
            instructions.append(
                Instruction(
                    OpCode.WRITE_TEXT,
                    context.consume(argument),
                    instruction.source_start,
                )
            )
        elif instruction.opcode is OpCode.WRITE_DOT:
            instructions.append(
                _escape_dot(instruction, context.escape_kinds(instruction.source_start))
            )
        elif instruction.opcode is OpCode.WRITE_PIPELINE:
            instructions.append(
                _escape_pipeline(
                    instruction, context.escape_kinds(instruction.source_start)
                )
            )
        elif instruction.opcode is OpCode.CALL_TEMPLATE:
            target = instruction.argument
            assert isinstance(target, CallTarget)
            instructions.append(
                Instruction(
                    OpCode.CALL_TEMPLATE,
                    CallTarget(call_names.get(index, target.name), target.pipeline),
                    instruction.source_start,
                )
            )
        else:
            instructions.append(instruction)
    return Program(
        tuple(instructions),
        name=name,
        source=program.source,
        source_name=program.source_name,
    ), output


def _propagate_contexts(
    program: Program,
    start: Context,
    *,
    resolve: _CallResolver,
    call_names: dict[int, str],
) -> tuple[dict[int, Context], Context]:
    if not program.instructions:
        return {}, replace(start)
    incoming = {0: replace(start)}
    output: Context | None = None
    pending = deque([0])
    while pending:
        index = pending.popleft()
        instruction = program.instructions[index]
        outgoing = _transfer_context(
            incoming[index],
            instruction,
            resolve=resolve,
            call_names=call_names,
            index=index,
        )
        for successor in _successors(index, instruction):
            if successor >= len(program.instructions):
                output = (
                    outgoing
                    if output is None
                    else _join_contexts(
                        output,
                        outgoing,
                        position=instruction.source_start,
                    )
                )
                continue
            previous = incoming.get(successor)
            merged = (
                outgoing
                if previous is None
                else _join_contexts(
                    previous,
                    outgoing,
                    position=program.instructions[successor].source_start,
                )
            )
            if previous != merged:
                incoming[successor] = merged
                pending.append(successor)
    return incoming, output if output is not None else replace(start)


def _transfer_context(
    context: Context,
    instruction: Instruction,
    *,
    resolve: _CallResolver,
    call_names: dict[int, str],
    index: int,
) -> Context:
    result = replace(context)
    if instruction.opcode is OpCode.WRITE_TEXT:
        argument = instruction.argument
        assert isinstance(argument, str)
        result.consume(argument)
    elif instruction.opcode in {OpCode.WRITE_DOT, OpCode.WRITE_PIPELINE}:
        result.escape_kinds(instruction.source_start)
    elif instruction.opcode is OpCode.CALL_TEMPLATE:
        target = instruction.argument
        assert isinstance(target, CallTarget)
        variant_name, result = resolve(target.name, result)
        call_names[index] = variant_name
    return result


def _context_key(context: Context) -> _ContextKey:
    return tuple(getattr(context, field.name) for field in fields(Context))


def _variant_name(name: str, context: Context) -> str:
    delimiter = {'"': "double", "'": "single", "": "none"}[context.delimiter]
    element = context.element or "none"
    closing = "closing" if context.closing_tag else "open"
    identity = blake2s(repr(_context_key(context)).encode(), digest_size=6).hexdigest()
    return (
        f"{name}$htmltemplate_{context.kind.name.lower()}_{delimiter}_"
        f"{element}_{closing}_{context.attribute.name.lower()}_"
        f"{context.url_part.name.lower()}_{context.js_context.name.lower()}_{identity}"
    )


def _successors(index: int, instruction: Instruction) -> tuple[int, ...]:
    next_index = index + 1
    if instruction.opcode in {OpCode.JUMP, OpCode.BREAK_RANGE}:
        target = instruction.argument
        assert isinstance(target, int)
        return (target,)
    if instruction.opcode in {OpCode.JUMP_IF_FALSE, OpCode.ENTER_WITH}:
        target = instruction.argument
        assert isinstance(target, BranchTarget)
        return (next_index, target.target)
    if instruction.opcode is OpCode.ITERATE:
        target = instruction.argument
        assert isinstance(target, RangeTarget)
        return (next_index, target.empty_target)
    if instruction.opcode is OpCode.NEXT_ITERATION:
        target = instruction.argument
        assert isinstance(target, RangeNextTarget)
        return (target.body_target, target.exit_target)
    return (next_index,)


def _join_contexts(
    left: Context,
    right: Context,
    *,
    position: int,
    allow_nudge: bool = True,
) -> Context:
    if left == right:
        return left
    differing = {
        field.name
        for field in fields(Context)
        if getattr(left, field.name) != getattr(right, field.name)
    }
    if differing == {"url_part"}:
        return replace(left, url_part=URLPart.UNKNOWN)
    if differing == {"js_context"}:
        return replace(left, js_context=JSContext.UNKNOWN)
    if allow_nudge:
        nudged_left = _nudge_context(left)
        nudged_right = _nudge_context(right)
        if nudged_left != left or nudged_right != right:
            return _join_contexts(
                nudged_left,
                nudged_right,
                position=position,
                allow_nudge=False,
            )
    raise TemplateSyntaxError(
        "branches end in different HTML contexts",
        position=position,
    )


def _nudge_context(context: Context) -> Context:
    nudged = replace(context)
    if nudged.kind in {ContextKind.TAG, ContextKind.AFTER_NAME}:
        nudged.kind = ContextKind.ATTR_NAME
        nudged.attribute = AttributeKind.PLAIN
        nudged.attribute_name = ""
        nudged.url_part = URLPart.NONE
    elif nudged.kind is ContextKind.ATTR_NAME:
        nudged.attribute_name = ""
    elif nudged.kind is ContextKind.BEFORE_VALUE:
        nudged.escape_kinds()
    return nudged


def _escape_dot(instruction: Instruction, kinds: tuple[EscapeKind, ...]) -> Instruction:
    pipeline = CompiledPipeline(
        (),
        False,
        (
            CompiledCommand((Operand(OperandKind.DOT),)),
            *(_escaper_command(kind) for kind in kinds),
        ),
        instruction.source_start,
    )
    return Instruction(OpCode.WRITE_PIPELINE, pipeline, instruction.source_start)


def _escape_pipeline(
    instruction: Instruction, kinds: tuple[EscapeKind, ...]
) -> Instruction:
    pipeline = instruction.argument
    assert isinstance(pipeline, CompiledPipeline)
    escaped = CompiledPipeline(
        pipeline.bindings,
        pipeline.is_assignment,
        _ensure_pipeline_contains(
            pipeline.commands,
            kinds,
            position=instruction.source_start,
        ),
        pipeline.source_start,
    )
    return Instruction(OpCode.WRITE_PIPELINE, escaped, instruction.source_start)


def _escaper_command(kind: EscapeKind) -> CompiledCommand:
    return _function_command(_ESCAPER_NAMES[kind])


def _ensure_pipeline_contains(
    commands: tuple[CompiledCommand, ...],
    kinds: tuple[EscapeKind, ...],
    *,
    position: int,
) -> tuple[CompiledCommand, ...]:
    desired = [_ESCAPER_NAMES[kind] for kind in kinds]
    rewritten = list(commands)
    for index, command in enumerate(rewritten):
        name = _command_name(command)
        if name not in _PREDEFINED_ESCAPERS:
            continue
        if index != len(rewritten) - 1 or (
            name == "html" and kinds == (EscapeKind.NOSPACE,)
        ):
            raise TemplateSyntaxError(
                f"predefined escaper {name!r} disallowed in template",
                position=position,
            )

    last_name = _command_name(rewritten[-1]) if rewritten else None
    if last_name in _PREDEFINED_ESCAPERS:
        last = rewritten[-1]
        if len(rewritten) == 1 and len(last.arguments) > 1:
            rewritten[-1] = CompiledCommand(
                (
                    replace(last.arguments[0], value="_html_template_eval_args"),
                    *last.arguments[1:],
                )
            )
            rewritten.append(_function_command(last_name))
        duplicate = False
        for index, name in enumerate(desired):
            if _normalize_escaper(name) == last_name:
                desired[index] = last_name
                duplicate = True
        if duplicate:
            rewritten.pop()

    inserted = {
        _normalize_escaper(name)
        for command in rewritten
        if (name := _command_name(command)) is not None
    }
    for name in desired:
        normalized = _normalize_escaper(name)
        if normalized in inserted:
            continue
        previous = _command_name(rewritten[-1]) if rewritten else None
        if previous is not None and name in _REDUNDANT_ESCAPERS.get(
            previous, frozenset()
        ):
            continue
        rewritten.append(_function_command(name))
        inserted.add(normalized)
    return tuple(rewritten)


def _command_name(command: CompiledCommand) -> str | None:
    first = command.arguments[0]
    return (
        first.value
        if first.kind is OperandKind.FUNCTION and isinstance(first.value, str)
        else None
    )


def _normalize_escaper(name: str) -> str:
    return _EQUIVALENT_ESCAPERS.get(name, name)


def _function_command(name: str) -> CompiledCommand:
    return CompiledCommand((Operand(OperandKind.FUNCTION, name),))
