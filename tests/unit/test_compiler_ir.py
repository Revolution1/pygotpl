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
    compile_template,
)
from gotpl.parse import (
    ActionNode,
    ParsedTemplate,
    TemplateCallNode,
    parse,
    parse_template,
)


def field_pipeline(name: str) -> CompiledPipeline:
    return CompiledPipeline(
        (),
        False,
        (CompiledCommand((Operand(OperandKind.FIELD, fields=(name,)),)),),
    )


def test_compiler_keeps_non_dot_actions_as_pipeline_operations() -> None:
    root = parse('{{printf "%s" .Name}}')
    action = root.nodes[0]
    assert isinstance(action, ActionNode)

    program = compile_template(root)

    expected = CompiledPipeline(
        (),
        False,
        (
            CompiledCommand(
                (
                    Operand(OperandKind.FUNCTION, "printf"),
                    Operand(OperandKind.STRING, "%s"),
                    Operand(OperandKind.FIELD, fields=("Name",)),
                )
            ),
        ),
    )
    assert program.instructions == (
        Instruction(OpCode.WRITE_PIPELINE, expected, action.start),
    )


def test_compiler_emits_patched_if_control_flow() -> None:
    parsed = parse("{{if .Ready}}yes{{else}}no{{end}}")
    program = compile_template(parsed)

    assert program.instructions == (
        Instruction(OpCode.PUSH_SCOPE, None, 0),
        Instruction(OpCode.JUMP_IF_FALSE, BranchTarget(field_pipeline("Ready"), 4), 0),
        Instruction(OpCode.WRITE_TEXT, "yes", 13),
        Instruction(OpCode.JUMP, 5, 16),
        Instruction(OpCode.WRITE_TEXT, "no", 24),
        Instruction(OpCode.POP_SCOPE, None, 33),
    )


def test_compiler_emits_with_scope_operations() -> None:
    root = parse("{{with .User}}{{.}}{{else}}none{{end}}")

    program = compile_template(root)

    assert program.instructions == (
        Instruction(OpCode.PUSH_SCOPE, None, 0),
        Instruction(OpCode.ENTER_WITH, BranchTarget(field_pipeline("User"), 5), 0),
        Instruction(OpCode.WRITE_DOT, None, 14),
        Instruction(OpCode.EXIT_WITH, None, 19),
        Instruction(OpCode.JUMP, 6, 19),
        Instruction(OpCode.WRITE_TEXT, "none", 27),
        Instruction(OpCode.POP_SCOPE, None, 38),
    )


def test_compiler_resolves_range_break_and_continue_targets() -> None:
    root = parse("{{range .Items}}a{{continue}}b{{break}}c{{else}}empty{{end}}")

    program = compile_template(root)

    assert program.instructions == (
        Instruction(OpCode.PUSH_SCOPE, None, 0),
        Instruction(
            OpCode.ITERATE,
            RangeTarget(field_pipeline("Items"), 8, 9),
            0,
        ),
        Instruction(OpCode.WRITE_TEXT, "a", 16),
        Instruction(OpCode.JUMP, 7, 17),
        Instruction(OpCode.WRITE_TEXT, "b", 29),
        Instruction(OpCode.BREAK_RANGE, 9, 30),
        Instruction(OpCode.WRITE_TEXT, "c", 39),
        Instruction(OpCode.NEXT_ITERATION, RangeNextTarget(2, 9), 40),
        Instruction(OpCode.WRITE_TEXT, "empty", 48),
        Instruction(OpCode.POP_SCOPE, None, 60),
    )


def test_compiler_builds_named_programs_and_template_calls() -> None:
    parsed = parse_template(
        '{{define "item"}}item{{end}}{{template "item" .}}', name="root"
    )
    call = parsed.root.nodes[0]
    assert isinstance(parsed, ParsedTemplate)
    assert isinstance(call, TemplateCallNode)

    program = compile_template(parsed)

    assert program.name == "root"
    assert program.instructions == (
        Instruction(
            OpCode.CALL_TEMPLATE,
            CallTarget(
                call.name,
                CompiledPipeline(
                    (),
                    False,
                    (CompiledCommand((Operand(OperandKind.DOT),)),),
                ),
            ),
            call.start,
        ),
    )
    assert program.definitions == (
        Program(
            (Instruction(OpCode.WRITE_TEXT, "item", 17),),
            name="item",
        ),
    )


def test_compiler_encodes_every_operand_kind_and_bindings() -> None:
    root = parse(
        "{{$value := .}}"
        "{{$out := call nil true 42 1+2i 'x' $value.Name (.Inner | render).Result}}",
        functions={"render"},
    )

    pipeline = compile_template(root).instructions[1].argument

    assert isinstance(pipeline, CompiledPipeline)
    assert pipeline.bindings == ("$out",)
    assert pipeline.is_assignment is False
    assert [operand.kind for operand in pipeline.commands[0].arguments] == [
        OperandKind.FUNCTION,
        OperandKind.NIL,
        OperandKind.BOOL,
        OperandKind.NUMBER,
        OperandKind.COMPLEX,
        OperandKind.CHARACTER,
        OperandKind.VARIABLE,
        OperandKind.SUBPIPELINE,
    ]
    variable = pipeline.commands[0].arguments[6]
    assert variable.value == "$value"
    assert variable.fields == ("Name",)
    grouped = pipeline.commands[0].arguments[7]
    assert grouped.fields == ("Result",)
    assert grouped.pipeline is not None


def test_compiler_handles_empty_and_no_else_control_bodies() -> None:
    program = compile_template(
        parse("{{if .}}{{end}}{{with .}}{{end}}{{range .}}{{end}}")
    )

    assert [instruction.opcode for instruction in program.instructions] == [
        OpCode.PUSH_SCOPE,
        OpCode.JUMP_IF_FALSE,
        OpCode.POP_SCOPE,
        OpCode.PUSH_SCOPE,
        OpCode.ENTER_WITH,
        OpCode.EXIT_WITH,
        OpCode.POP_SCOPE,
        OpCode.PUSH_SCOPE,
        OpCode.ITERATE,
        OpCode.NEXT_ITERATION,
        OpCode.POP_SCOPE,
    ]
    first = program.instructions[1].argument
    enter = program.instructions[4].argument
    iteration = program.instructions[8].argument
    assert isinstance(first, BranchTarget)
    assert isinstance(enter, BranchTarget)
    assert isinstance(iteration, RangeTarget)
    assert first.target == 2
    assert enter.target == 6
    assert iteration.empty_target == 10
    assert iteration.exit_target == 10


def test_compiler_emits_calls_without_pipelines_and_for_blocks() -> None:
    parsed = parse_template(
        '{{define "item"}}x{{end}}{{template "item"}}{{block "fallback" .}}y{{end}}'
    )

    program = compile_template(parsed)

    first = program.instructions[0].argument
    second = program.instructions[1].argument
    assert first == CallTarget("item", None)
    assert isinstance(second, CallTarget)
    assert [item.name for item in program.definitions] == ["item", "fallback"]
