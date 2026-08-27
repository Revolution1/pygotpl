# pyright: reportPrivateUsage=false

from collections.abc import Iterable
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
from gotpl.runtime import INVALID, render_program, sync_vm


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
def test_runtime_rejects_invalid_instruction_arguments(opcode: OpCode) -> None:
    program = Program((Instruction(opcode, None, 0),))

    with pytest.raises(gotpl.TemplateExecutionError, match="invalid argument"):
        render_program(program)


def test_runtime_rejects_unknown_opcodes() -> None:
    class UnknownOpcode:
        name = "UNKNOWN"

    instruction = Instruction(cast(OpCode, UnknownOpcode()), None, 0)

    with pytest.raises(gotpl.TemplateExecutionError, match="not implemented"):
        render_program(Program((instruction,)))


def test_runtime_enforces_template_call_depth() -> None:
    with pytest.raises(
        gotpl.TemplateExecutionError,
        match=r"exceeded maximum template depth \(100000\)",
    ):
        render_program(Program(()), _depth=100_000)

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
        render_program(recursive, _depth=99_999)


def test_runtime_uses_explicit_frames_for_deep_finite_template_calls() -> None:
    assert render_program(finite_template_call_chain(1_500)) == "done"


def test_execution_contexts_reuse_immutable_value_adapters() -> None:
    first = sync_vm._ExecutionContext(None, None, {}, "default")
    second = sync_vm._ExecutionContext(None, None, {}, "default")
    strict = sync_vm._ExecutionContext(None, None, {}, "error")

    assert first.adapter is second.adapter
    assert first.adapter is not strict.adapter
    assert first.scopes is None
    assert first.dot_stack is None
    assert first.ranges is None


def test_execution_location_derives_diagnostics_from_the_current_program() -> None:
    location = sync_vm._ExecutionLocation()
    assert location.source == ""
    assert location.source_name == "template"
    assert location.template_name == "template"

    location = sync_vm._ExecutionLocation(
        Program((), name="block", source="template source", source_name="file.tpl")
    )

    assert location.source == "template source"
    assert location.source_name == "file.tpl"
    assert location.template_name == "block"


def test_runtime_rejects_an_undefined_template() -> None:
    instruction = Instruction(
        OpCode.CALL_TEMPLATE,
        CallTarget("absent", None),
        0,
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        render_program(Program((instruction,)))


def test_runtime_rejects_an_unregistered_function_in_manual_ir() -> None:
    instruction = Instruction(
        OpCode.WRITE_PIPELINE,
        pipeline(Operand(OperandKind.FUNCTION, "absent")),
        0,
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        render_program(Program((instruction,)))


def test_runtime_rejects_an_unregistered_function_used_as_an_operand() -> None:
    instruction = Instruction(
        OpCode.WRITE_PIPELINE,
        pipeline(
            Operand(OperandKind.FUNCTION, "printf"),
            Operand(OperandKind.STRING, "%s"),
            Operand(OperandKind.FUNCTION, "absent"),
        ),
        0,
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="not defined"):
        render_program(Program((instruction,)))


def test_runtime_rejects_a_non_string_function_name_in_manual_ir() -> None:
    instruction = Instruction(
        OpCode.WRITE_PIPELINE,
        pipeline(Operand(OperandKind.FUNCTION, True)),
        0,
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="function name"):
        render_program(Program((instruction,)))


def test_runtime_rejects_non_callable_commands_with_arguments() -> None:
    instruction = Instruction(
        OpCode.WRITE_PIPELINE,
        pipeline(
            Operand(OperandKind.STRING, "value"),
            Operand(OperandKind.STRING, "argument"),
        ),
        0,
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="non-callable"):
        render_program(Program((instruction,)))


def test_runtime_appends_pipeline_values_to_non_function_commands() -> None:
    chained = CompiledPipeline(
        (),
        False,
        (
            CompiledCommand((Operand(OperandKind.STRING, "first"),)),
            CompiledCommand((Operand(OperandKind.STRING, "second"),)),
        ),
    )

    with pytest.raises(gotpl.TemplateExecutionError, match="non-callable"):
        render_program(Program((Instruction(OpCode.WRITE_PIPELINE, chained, 0),)))


def test_execution_context_covers_missing_and_assignment_paths() -> None:
    context = sync_vm._ExecutionContext(None, None, {}, "default")
    assert context.lookup_variable("$missing") is INVALID
    assert context.lookup_variable("$") is None
    context.set_variable("$value", 1, assignment=False)
    context.set_variable("$value", 2, assignment=True)
    assert context.lookup_variable("$value") == 2
    context.set_variable("$", "changed", assignment=True)
    assert context.lookup_variable("$") == "changed"
    with pytest.raises(gotpl.TemplateExecutionError, match="undefined variable"):
        context.set_variable("$absent", 1, assignment=True)

    context.pop_scope()
    with pytest.raises(gotpl.TemplateExecutionError, match="scope exit"):
        context.pop_scope()

    assert (
        sync_vm._evaluate_pipeline(  # pyright: ignore[reportPrivateUsage]
            pipeline(Operand(OperandKind.STRING, "value")), context
        )
        == "value"
    )


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
def test_runtime_rejects_validly_shaped_stateful_opcodes_without_state(
    instruction: Instruction,
    message: str,
) -> None:
    with pytest.raises(gotpl.TemplateExecutionError, match=message):
        render_program(Program((instruction,)))


def test_runtime_lazily_allocates_nested_with_and_range_stacks() -> None:
    source = "{{with .}}{{with .}}W{{end}}{{end}}/{{range .}}{{range $}}R{{end}}{{end}}"

    assert gotpl.render(source, [[1]]) == "W/R"
    assert gotpl.render("{{range .}}{{range $}}B{{break}}{{end}}{{end}}", [[1]]) == (
        "B"
    )


def test_operand_decoder_defends_against_malformed_manual_ir() -> None:
    context = sync_vm._ExecutionContext(None, None, {}, "default")
    assert (
        sync_vm._evaluate_operand(Operand(OperandKind.SUBPIPELINE), context) is INVALID
    )

    class UnknownOperand:
        name = "UNKNOWN"

    malformed = Operand(cast(OperandKind, UnknownOperand()))
    with pytest.raises(gotpl.TemplateExecutionError, match="not directly evaluable"):
        sync_vm._evaluate_operand(malformed, context)


def test_runtime_handles_python_only_iterables_and_range_errors() -> None:
    values: Iterable[str] = (value for value in ("a", "b"))
    assert gotpl.render("{{range .}}{{.}}{{end}}", values) == "ab"
    with pytest.raises(gotpl.TemplateExecutionError, match="cannot iterate"):
        gotpl.render("{{range .}}{{.}}{{end}}", "not iterable by Go rules")


def test_runtime_covers_mapping_range_single_binding_and_false_with() -> None:
    assert (
        gotpl.render("{{range $value := .}}{{$value}}{{end}}", {"b": 2, "a": 1}) == "12"
    )
    assert gotpl.render("{{with .missing}}yes{{else}}no{{end}}", {}) == "no"


def test_runtime_formats_nil_characters_and_printf_special_values() -> None:
    assert gotpl.render("{{'A'}}/{{printf \"%v/%v\" true nil}}") == "65/true/<nil>"


def test_call_builtin_invokes_python_function_values() -> None:
    def triple(value: int) -> int:
        return value * 3

    assert gotpl.render("{{call .function 2}}", {"function": triple}) == "6"


def test_call_builtin_validates_target_annotations_before_invocation() -> None:
    def upper(value: str) -> str:
        return value.upper()

    with pytest.raises(gotpl.TemplateExecutionError, match="expected str, got int"):
        gotpl.render("{{call .function 2}}", {"function": upper})


def test_bound_method_exceptions_are_translated_and_chained() -> None:
    failure = RuntimeError("method failed")

    class Subject:
        def fail(self) -> None:
            raise failure

    with pytest.raises(gotpl.TemplateExecutionError, match="method failed") as captured:
        gotpl.render("{{.fail}}", Subject())
    assert captured.value.__cause__ is failure


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{{and}}", "requires an argument"),
        ("{{eq 1}}", "at least two arguments"),
        ("{{len 1}}", "has no length"),
        ("{{printf 1}}", "format must be a string"),
        ('{{index "abc" "x"}}', "index must be an integer"),
        ('{{index "abc" true}}', "index must be an integer"),
        ('{{index "abc" -1}}', "out of range"),
        ("{{index 1 0}}", "cannot index"),
        ("{{slice 1}}", "cannot slice"),
        ('{{slice "abc" "x"}}', "integer indexes"),
        ('{{slice "abc" true}}', "integer indexes"),
        ('{{slice "abc" 0 1 2}}', "three-index slice"),
        ('{{slice "abc" 0 4}}', "out of bounds"),
        ("{{call 1}}", "not callable"),
    ],
)
def test_builtin_errors_are_translated(template: str, message: str) -> None:
    with pytest.raises(gotpl.TemplateExecutionError, match=message):
        gotpl.render(template)


def test_number_decoder_defends_against_malformed_manual_ir() -> None:
    assert sync_vm._number_value(True, is_complex=False) is INVALID
    assert sync_vm._number_value("1i", is_complex=False) == 1j
    assert sync_vm._number_value("1+2i", is_complex=True) == 1 + 2j
    assert sync_vm._number_value("2", is_complex=True) == 2 + 0j
    assert sync_vm._number_value("0x1p2", is_complex=False) == 4.0
    assert sync_vm._number_value("0b10", is_complex=False) == 2
    assert sync_vm._number_value("010", is_complex=False) == 8


def test_comparisons_cover_float_complex_nil_and_cross_kind_rules() -> None:
    assert gotpl.render("{{eq 1.5 1.5}}/{{eq 1i 1i}}") == "true/true"
    assert gotpl.render("{{eq nil .}}", []) == "false"
    with pytest.raises(gotpl.TemplateExecutionError, match="incompatible"):
        gotpl.render("{{eq nil 1}}")
    with pytest.raises(gotpl.TemplateExecutionError, match="incompatible"):
        gotpl.render("{{lt 1 1.0}}")


@pytest.mark.parametrize("value", [(1,), b"x", bytearray(b"x"), frozenset({1})])
def test_python_slice_like_values_are_not_comparable(value: object) -> None:
    with pytest.raises(gotpl.TemplateExecutionError, match="non-comparable"):
        gotpl.render("{{eq .left .right}}", {"left": value, "right": value})

    assert gotpl.render("{{eq nil .}}", value) == "false"


def test_go_pointer_equality_uses_identity_and_supports_typed_nil() -> None:
    target = object()
    same_left = gotpl.GoPointer(target, target_type="widget")
    same_right = gotpl.GoPointer(target, target_type="widget")
    other = gotpl.GoPointer(object(), target_type="widget")
    nil_pointer = gotpl.GoPointer[object](None, target_type="widget")

    assert gotpl.render(
        "{{eq .left .right}}", {"left": same_left, "right": same_right}
    ) == ("true")
    assert gotpl.render("{{eq .left .right}}", {"left": same_left, "right": other}) == (
        "false"
    )
    assert gotpl.render("{{eq nil .}}", nil_pointer) == "true"
    with pytest.raises(gotpl.TemplateExecutionError, match="incompatible"):
        gotpl.render(
            "{{eq .left .right}}",
            {
                "left": same_left,
                "right": gotpl.GoPointer(target, target_type="other"),
            },
        )
