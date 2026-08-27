"""Compilation from source-mapped syntax trees to compact instructions."""

from dataclasses import dataclass

from gotpl.parse.nodes import (
    ActionNode,
    BoolNode,
    BreakNode,
    CharacterNode,
    CommandNode,
    ComplexNode,
    ContinueNode,
    DefinitionNode,
    DotNode,
    FieldNode,
    IdentifierNode,
    IfNode,
    ListNode,
    NilNode,
    NumberNode,
    ParsedTemplate,
    PipeNode,
    RangeNode,
    StringNode,
    TemplateNode,
    TermNode,
    TextNode,
    VariableNode,
    WithNode,
)

from .instructions import (
    BranchTarget,
    CallTarget,
    CompiledCommand,
    CompiledPipeline,
    Instruction,
    InstructionArgument,
    OpCode,
    Operand,
    OperandKind,
    Program,
    RangeNextTarget,
    RangeTarget,
)


@dataclass(slots=True)
class _LoopContext:
    break_sites: list[int]
    continue_sites: list[int]


def compile_template(root: ListNode | ParsedTemplate, *, source: str = "") -> Program:
    """Compile a parsed template tree into an immutable program."""

    if isinstance(root, ParsedTemplate):
        definitions = tuple(
            _compile_definition(item, source=source, source_name=root.name)
            for item in root.definitions
        )
        return Program(
            _Compiler().compile_list(root.root),
            name=root.name,
            definitions=definitions,
            source=source,
            source_name=root.name,
        )
    return Program(_Compiler().compile_list(root), source=source)


def _compile_definition(
    definition: DefinitionNode, *, source: str, source_name: str
) -> Program:
    return Program(
        _Compiler().compile_list(definition.body),
        name=definition.name,
        source=source,
        source_name=source_name,
    )


class _Compiler:
    def __init__(self) -> None:
        self.instructions: list[Instruction] = []
        self.loops: list[_LoopContext] = []

    def compile_list(self, root: ListNode) -> tuple[Instruction, ...]:
        self.emit_list(root)
        return tuple(self.instructions)

    def emit_list(self, root: ListNode) -> None:
        for node in root.nodes:
            self.emit_node(node)

    def emit_node(self, node: TemplateNode) -> None:
        if isinstance(node, TextNode):
            self.emit(OpCode.WRITE_TEXT, node.text, node.start)
        elif isinstance(node, ActionNode):
            self.emit_action(node)
        elif isinstance(node, IfNode):
            self.emit_if(node)
        elif isinstance(node, WithNode):
            self.emit_with(node)
        elif isinstance(node, RangeNode):
            self.emit_range(node)
        elif isinstance(node, BreakNode):
            self.emit_loop_jump(node.start, is_break=True)
        elif isinstance(node, ContinueNode):
            self.emit_loop_jump(node.start, is_break=False)
        else:
            self.emit_call(node.name, node.pipeline, node.start)

    def emit_action(self, node: ActionNode) -> None:
        if node.pipeline.declarations:
            self.emit(
                OpCode.EVAL_PIPELINE, _compile_pipeline(node.pipeline), node.start
            )
        elif _is_plain_dot(node.pipeline):
            self.emit(OpCode.WRITE_DOT, None, node.start)
        else:
            self.emit(
                OpCode.WRITE_PIPELINE, _compile_pipeline(node.pipeline), node.start
            )

    def emit_if(self, node: IfNode) -> None:
        self.emit(OpCode.PUSH_SCOPE, None, node.start)
        condition = self.emit(
            OpCode.JUMP_IF_FALSE,
            BranchTarget(_compile_pipeline(node.pipeline), -1),
            node.start,
        )
        self.emit_list(node.body)
        if node.else_body is None:
            exit_scope = self.emit(
                OpCode.POP_SCOPE, None, _list_end(node.body, node.start)
            )
            self.patch_branch(condition, exit_scope)
            return
        jump = self.emit(OpCode.JUMP, -1, _list_end(node.body, node.start))
        self.patch_branch(condition, len(self.instructions))
        self.emit_list(node.else_body)
        exit_scope = self.emit(OpCode.POP_SCOPE, None, node.end)
        self.patch_jump(jump, exit_scope)

    def emit_with(self, node: WithNode) -> None:
        self.emit(OpCode.PUSH_SCOPE, None, node.start)
        enter = self.emit(
            OpCode.ENTER_WITH,
            BranchTarget(_compile_pipeline(node.pipeline), -1),
            node.start,
        )
        self.emit_list(node.body)
        body_end = _list_end(node.body, node.start)
        self.emit(OpCode.EXIT_WITH, None, body_end)
        if node.else_body is None:
            exit_scope = self.emit(OpCode.POP_SCOPE, None, body_end)
            self.patch_branch(enter, exit_scope)
            return
        jump = self.emit(OpCode.JUMP, -1, body_end)
        self.patch_branch(enter, len(self.instructions))
        self.emit_list(node.else_body)
        exit_scope = self.emit(OpCode.POP_SCOPE, None, node.end)
        self.patch_jump(jump, exit_scope)

    def emit_range(self, node: RangeNode) -> None:
        self.emit(OpCode.PUSH_SCOPE, None, node.start)
        iterate = self.emit(
            OpCode.ITERATE,
            RangeTarget(_compile_pipeline(node.pipeline), -1, -1),
            node.start,
        )
        body_start = len(self.instructions)
        loop = _LoopContext([], [])
        self.loops.append(loop)
        self.emit_list(node.body)
        self.loops.pop()
        next_site = self.emit(
            OpCode.NEXT_ITERATION,
            RangeNextTarget(body_start, -1),
            _list_end(node.body, node.start),
        )
        for site in loop.continue_sites:
            self.patch_jump(site, next_site)
        empty_target = len(self.instructions)
        if node.else_body is not None:
            self.emit_list(node.else_body)
        exit_scope = self.emit(OpCode.POP_SCOPE, None, node.end)
        self.patch_range_next(next_site, exit_scope)
        self.patch_range(iterate, empty_target, exit_scope)
        for site in loop.break_sites:
            self.patch_jump(site, exit_scope)

    def emit_loop_jump(self, source_start: int, *, is_break: bool) -> None:
        opcode = OpCode.BREAK_RANGE if is_break else OpCode.JUMP
        site = self.emit(opcode, -1, source_start)
        loop = self.loops[-1]
        (loop.break_sites if is_break else loop.continue_sites).append(site)

    def emit_call(self, name: str, pipeline: PipeNode | None, start: int) -> None:
        compiled = None if pipeline is None else _compile_pipeline(pipeline)
        self.emit(OpCode.CALL_TEMPLATE, CallTarget(name, compiled), start)

    def emit(
        self, opcode: OpCode, argument: InstructionArgument, source_start: int
    ) -> int:
        index = len(self.instructions)
        self.instructions.append(Instruction(opcode, argument, source_start))
        return index

    def patch_jump(self, index: int, target: int) -> None:
        instruction = self.instructions[index]
        self.instructions[index] = Instruction(
            instruction.opcode, target, instruction.source_start
        )

    def patch_branch(self, index: int, target: int) -> None:
        instruction = self.instructions[index]
        argument = instruction.argument
        assert isinstance(argument, BranchTarget)
        self.instructions[index] = Instruction(
            instruction.opcode,
            BranchTarget(argument.pipeline, target),
            instruction.source_start,
        )

    def patch_range(self, index: int, empty_target: int, exit_target: int) -> None:
        instruction = self.instructions[index]
        argument = instruction.argument
        assert isinstance(argument, RangeTarget)
        self.instructions[index] = Instruction(
            instruction.opcode,
            RangeTarget(argument.pipeline, empty_target, exit_target),
            instruction.source_start,
        )

    def patch_range_next(self, index: int, exit_target: int) -> None:
        instruction = self.instructions[index]
        argument = instruction.argument
        assert isinstance(argument, RangeNextTarget)
        self.instructions[index] = Instruction(
            instruction.opcode,
            RangeNextTarget(argument.body_target, exit_target),
            instruction.source_start,
        )


def _is_plain_dot(pipeline: PipeNode) -> bool:
    return (
        not pipeline.declarations
        and len(pipeline.commands) == 1
        and len(pipeline.commands[0].arguments) == 1
        and isinstance(pipeline.commands[0].arguments[0], DotNode)
    )


def _compile_pipeline(pipeline: PipeNode) -> CompiledPipeline:
    return CompiledPipeline(
        tuple(variable.name for variable in pipeline.declarations),
        pipeline.is_assignment,
        tuple(_compile_command(command) for command in pipeline.commands),
        pipeline.start,
    )


def _compile_command(command: CommandNode) -> CompiledCommand:
    return CompiledCommand(tuple(_compile_operand(item) for item in command.arguments))


def _compile_operand(node: TermNode) -> Operand:
    if isinstance(node, DotNode):
        return Operand(OperandKind.DOT)
    if isinstance(node, NilNode):
        return Operand(OperandKind.NIL)
    if isinstance(node, BoolNode):
        return Operand(OperandKind.BOOL, node.value)
    if isinstance(node, NumberNode):
        return Operand(OperandKind.NUMBER, node.text)
    if isinstance(node, ComplexNode):
        return Operand(OperandKind.COMPLEX, node.text)
    if isinstance(node, StringNode):
        return Operand(OperandKind.STRING, node.value)
    if isinstance(node, CharacterNode):
        return Operand(OperandKind.CHARACTER, node.value)
    if isinstance(node, IdentifierNode):
        return Operand(OperandKind.FUNCTION, node.name)
    if isinstance(node, FieldNode):
        return Operand(OperandKind.FIELD, fields=node.fields)
    if isinstance(node, VariableNode):
        return Operand(OperandKind.VARIABLE, node.name, node.fields)
    return Operand(
        OperandKind.SUBPIPELINE,
        fields=node.fields,
        pipeline=_compile_pipeline(node.pipeline),
    )


def _list_end(nodes: ListNode, fallback: int) -> int:
    if not nodes.nodes:
        return fallback
    return nodes.nodes[-1].end
