# pyright: reportPrivateUsage=false

from typing import cast

import pytest

import gotpl
from gotpl.compile import (
    CallTarget,
    CompiledCommand,
    CompiledPipeline,
    Instruction,
    OpCode,
    Operand,
    OperandKind,
    Program,
    RangeNextTarget,
)
from gotpl.runtime import INVALID, async_vm, render_program_async


def pipeline(*operands: Operand) -> CompiledPipeline:
    return CompiledPipeline((), False, (CompiledCommand(operands),))


def finite_template_call_chain(length: int) -> Program:
    definitions = tuple(
        Program(
            (
                Instruction(
                    OpCode.WRITE_TEXT if index == length - 1 else OpCode.CALL_TEMPLATE,
                    "done"
                    if index == length - 1
                    else CallTarget(f"chain-{index + 1}", None),
                    0,
                ),
            ),
            name=f"chain-{index}",
        )
        for index in range(length)
    )
    return Program(
        (Instruction(OpCode.CALL_TEMPLATE, CallTarget("chain-0", None), 0),),
        definitions=definitions,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "opcode",
    [
        OpCode.WRITE_PIPELINE,
        OpCode.EVAL_PIPELINE,
        OpCode.JUMP_IF_FALSE,
        OpCode.ENTER_WITH,
        OpCode.ITERATE,
        OpCode.NEXT_ITERATION,
        OpCode.CALL_TEMPLATE,
        OpCode.BREAK_RANGE,
        OpCode.JUMP,
    ],
)
async def test_async_runtime_rejects_invalid_instruction_arguments(
    opcode: OpCode,
) -> None:
    program = Program((Instruction(opcode, None, 0),))

    with pytest.raises(gotpl.TemplateExecutionError, match="invalid argument"):
        await render_program_async(program)


@pytest.mark.asyncio
async def test_async_runtime_rejects_unknown_opcodes() -> None:
    class UnknownOpcode:
        name = "UNKNOWN"

    instruction = Instruction(cast(OpCode, UnknownOpcode()), None, 0)

    with pytest.raises(gotpl.TemplateExecutionError, match="not implemented"):
        await render_program_async(Program((instruction,)))


@pytest.mark.asyncio
async def test_async_runtime_enforces_template_call_depth() -> None:
    with pytest.raises(
        gotpl.TemplateExecutionError,
        match=r"exceeded maximum template depth \(100000\)",
    ):
        await render_program_async(Program(()), _depth=100_000)

    recursive = Program(
        (Instruction(OpCode.CALL_TEMPLATE, CallTarget("leaf", None), 0),),
        definitions=(
            Program(
                (Instruction(OpCode.CALL_TEMPLATE, CallTarget("end", None), 0),),
                name="leaf",
            ),
            Program((), name="end"),
        ),
    )
    with pytest.raises(gotpl.TemplateExecutionError, match="maximum template depth"):
        await render_program_async(recursive, _depth=99_999)


@pytest.mark.asyncio
async def test_async_runtime_uses_explicit_frames_for_deep_finite_calls() -> None:
    assert await render_program_async(finite_template_call_chain(1_500)) == "done"


@pytest.mark.asyncio
async def test_async_runtime_rejects_an_undefined_template() -> None:
    program = Program(
        (Instruction(OpCode.CALL_TEMPLATE, CallTarget("absent", None), 0),)
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        await render_program_async(program)


@pytest.mark.asyncio
async def test_async_runtime_defends_against_malformed_commands() -> None:
    programs = [
        Program(
            (
                Instruction(
                    OpCode.WRITE_PIPELINE,
                    pipeline(Operand(OperandKind.FUNCTION, True)),
                    0,
                ),
            )
        ),
        Program(
            (
                Instruction(
                    OpCode.WRITE_PIPELINE,
                    pipeline(Operand(OperandKind.FUNCTION, "absent")),
                    0,
                ),
            )
        ),
        Program(
            (
                Instruction(
                    OpCode.WRITE_PIPELINE,
                    pipeline(
                        Operand(OperandKind.STRING, "value"),
                        Operand(OperandKind.STRING, "argument"),
                    ),
                    0,
                ),
            )
        ),
        Program(
            (
                Instruction(
                    OpCode.WRITE_PIPELINE,
                    pipeline(
                        Operand(OperandKind.FUNCTION, "printf"),
                        Operand(OperandKind.STRING, "%s"),
                        Operand(OperandKind.FUNCTION, "absent"),
                    ),
                    0,
                ),
            )
        ),
    ]

    for program in programs:
        with pytest.raises(gotpl.TemplateExecutionError):
            await render_program_async(program)


@pytest.mark.asyncio
async def test_async_operand_decoder_defends_against_malformed_ir() -> None:
    context = async_vm._ExecutionContext(None, None, {}, "default")
    assert (
        await async_vm._evaluate_operand(Operand(OperandKind.SUBPIPELINE), context)
        is INVALID
    )

    class UnknownOperand:
        name = "UNKNOWN"

    malformed = Operand(cast(OperandKind, UnknownOperand()))
    with pytest.raises(gotpl.TemplateExecutionError, match="not directly evaluable"):
        await async_vm._evaluate_operand(malformed, context)


@pytest.mark.asyncio
async def test_async_runtime_covers_remaining_semantic_paths() -> None:
    assert await gotpl.render_async("{{with .missing}}yes{{else}}no{{end}}", {}) == "no"
    assert await gotpl.render_async("{{$value := .}}{{$value}}", "bound") == "bound"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("instruction", "message"),
    [
        (Instruction(OpCode.EXIT_WITH, None, 0), "with exit"),
        (
            Instruction(OpCode.NEXT_ITERATION, RangeNextTarget(0, 1), 0),
            "range continuation",
        ),
        (Instruction(OpCode.BREAK_RANGE, 1, 0), "range break"),
    ],
)
async def test_async_runtime_rejects_stateful_opcodes_without_state(
    instruction: Instruction,
    message: str,
) -> None:
    with pytest.raises(gotpl.TemplateExecutionError, match=message):
        await render_program_async(Program((instruction,)))


@pytest.mark.asyncio
async def test_async_runtime_lazily_allocates_nested_control_stacks() -> None:
    source = "{{with .}}{{with .}}W{{end}}{{end}}/{{range .}}{{range $}}R{{end}}{{end}}"

    assert await gotpl.render_async(source, [[1]]) == "W/R"
    assert (
        await gotpl.render_async(
            "{{range .}}{{range $}}B{{break}}{{end}}{{end}}", [[1]]
        )
        == "B"
    )
    assert (
        await render_program_async(Program((Instruction(OpCode.WRITE_TEXT, None, 0),)))
        == ""
    )

    context = async_vm._ExecutionContext(None, None, {}, "default")
    assert (
        await async_vm._evaluate_pipeline(  # pyright: ignore[reportPrivateUsage]
            pipeline(Operand(OperandKind.STRING, "value")), context
        )
        == "value"
    )
    assert await gotpl.render_async("{{'A'}}") == "65"
    assert await gotpl.render_async("{{.missing.field}}", {}) == "<no value>"
    with pytest.raises(gotpl.TemplateExecutionError, match="requires an argument"):
        await gotpl.render_async("{{and}}")


@pytest.mark.asyncio
async def test_async_runtime_preserves_template_execution_errors_from_functions() -> (
    None
):
    failure = gotpl.TemplateExecutionError("direct failure")

    def fail() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.failure(failure)

    with pytest.raises(gotpl.TemplateExecutionError) as captured:
        await gotpl.render_async("{{fail}}", functions={"fail": fail})

    assert captured.value is failure


@pytest.mark.asyncio
async def test_async_runtime_appends_piped_values_to_non_function_commands() -> None:
    chained = CompiledPipeline(
        (),
        False,
        (
            CompiledCommand((Operand(OperandKind.STRING, "first"),)),
            CompiledCommand((Operand(OperandKind.STRING, "second"),)),
        ),
    )
    program = Program((Instruction(OpCode.WRITE_PIPELINE, chained, 0),))

    with pytest.raises(gotpl.TemplateExecutionError, match="non-callable"):
        await render_program_async(program)
