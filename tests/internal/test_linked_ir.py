# pyright: reportPrivateUsage=false

from io import StringIO

import pytest

from gotpl import Template
from gotpl.compile import CompiledPipeline, OpCode
from gotpl.errors import TemplateExecutionError
from gotpl.runtime import sync_vm
from gotpl.runtime.linked import (
    LinkedConstantOperand,
    LinkedDotOperand,
    LinkedFieldOperand,
    LinkedFieldPipeline,
    LinkedFunctionCommand,
    LinkedPipeline,
    LinkedVariableOperand,
    link_program,
)
from gotpl.runtime.sync_vm import render_linked_program, render_linked_program_to
from gotpl.runtime.values import INVALID


def test_link_program_aligns_specialized_writes_with_generic_instructions() -> None:
    template = Template('hello {{.User.Name}} {{printf "%s" .Label}}')

    linked = link_program(template._program, template._runtime_functions)

    assert linked.program is template._program
    assert len(linked.write_pipelines) == len(template._program.instructions)
    assert linked.write_pipelines[0] is None

    field = linked.write_pipelines[1]
    assert isinstance(field, LinkedFieldPipeline)
    assert field.fields == ("User", "Name")

    call = linked.write_pipelines[3]
    assert isinstance(call, LinkedPipeline)
    assert isinstance(call.commands[0], LinkedFunctionCommand)
    assert call.commands[0].name == "printf"
    assert call.commands[0].function is template._runtime_functions["printf"]
    assert call.commands[0].spec is template._runtime_functions.call_specs["printf"]

    assert [item.opcode for item in linked.program.instructions] == [
        OpCode.WRITE_TEXT,
        OpCode.WRITE_PIPELINE,
        OpCode.WRITE_TEXT,
        OpCode.WRITE_PIPELINE,
    ]


def test_link_program_aligns_lookup_control_pipelines() -> None:
    template = Template("{{range .Items}}{{if .Enabled}}{{.Name}}{{end}}{{end}}")

    linked = link_program(template._program, template._runtime_functions)

    assert linked.control_pipelines is not None
    iterate = linked.control_pipelines[1]
    branch = linked.control_pipelines[3]
    assert isinstance(iterate, LinkedFieldPipeline)
    assert iterate.fields == ("Items",)
    assert isinstance(branch, LinkedFieldPipeline)
    assert branch.fields == ("Enabled",)
    assert all(
        pipeline is None
        for index, pipeline in enumerate(linked.control_pipelines)
        if index not in {1, 3}
    )


def test_link_program_keeps_logical_control_pipelines_on_generic_fallback() -> None:
    template = Template("{{if and .Left .Right}}yes{{end}}")

    linked = link_program(template._program, template._runtime_functions)

    assert linked.control_pipelines is None


def test_link_program_keeps_logical_pipelines_on_generic_fallback() -> None:
    template = Template("{{and .Left .Right}}")

    linked = link_program(template._program, template._runtime_functions)

    assert linked.write_pipelines == (None,)


def test_linked_pipeline_matches_generic_value_and_function_evaluation() -> None:
    template = Template('{{printf "%s" .Name}}')
    instruction = template._program.instructions[0]
    linked = link_program(template._program, template._runtime_functions)
    linked_pipeline = linked.write_pipelines[0]
    assert isinstance(linked_pipeline, LinkedPipeline)
    generic_pipeline = instruction.argument
    assert isinstance(generic_pipeline, CompiledPipeline)
    context = sync_vm._ExecutionContext(
        {"Name": "Ada"},
        {"Name": "Ada"},
        template._runtime_functions,
        "default",
        template._runtime_functions.call_specs,
    )

    generic_value = sync_vm._evaluate_pipeline(generic_pipeline, context)
    linked_value = sync_vm._evaluate_linked_pipeline(linked_pipeline, context)

    assert generic_value == linked_value == "Ada"
    assert generic_value is not INVALID


def test_link_program_predecodes_static_function_operands() -> None:
    template = Template('{{printf "%s:%d:%t" "count" 010 true}}')

    linked = link_program(template._program, template._runtime_functions)

    pipeline = linked.write_pipelines[0]
    assert isinstance(pipeline, LinkedPipeline)
    command = pipeline.commands[0]
    assert isinstance(command, LinkedFunctionCommand)
    assert command.operands == (
        LinkedConstantOperand("%s:%d:%t"),
        LinkedConstantOperand("count"),
        LinkedConstantOperand(8),
        LinkedConstantOperand(True),
    )
    assert template.render() == "count:8:true"


def test_link_program_specializes_dynamic_function_operands() -> None:
    template = Template('{{$name := .Name}}{{printf "%v:%s:%s" . .User $name}}')

    linked = link_program(template._program, template._runtime_functions)

    pipeline = next(
        item for item in linked.write_pipelines if isinstance(item, LinkedPipeline)
    )
    command = pipeline.commands[0]
    assert isinstance(command, LinkedFunctionCommand)
    assert command.operands == (
        LinkedConstantOperand("%v:%s:%s"),
        LinkedDotOperand(),
        LinkedFieldOperand(("User",)),
        LinkedVariableOperand("$name", ()),
    )
    assert template.render({"Name": "Ada", "User": "admin"}) == (
        "map[Name:Ada User:admin]:admin:Ada"
    )


def test_linked_render_reuses_generic_control_flow_and_named_frames() -> None:
    template = Template(
        '{{define "card"}}{{if .Show}}{{printf "%s" .Name}}{{end}}{{end}}'
        '{{template "card" .}}'
    )
    linked = link_program(template._program, template._runtime_functions)
    data = {"Show": True, "Name": "Ada"}

    actual = render_linked_program(
        linked,
        data,
        functions=template._runtime_functions,
    )

    assert actual == template.render(data) == "Ada"


def test_linked_render_can_select_an_associated_template() -> None:
    template = Template(
        '{{define "main"}}{{template "leaf" .}}{{end}}'
        '{{define "leaf"}}{{.Value}}{{end}}'
    )
    linked = link_program(template._program, template._runtime_functions)

    actual = render_linked_program(
        linked,
        {"Value": "done"},
        functions=template._runtime_functions,
        template_name="main",
    )

    assert actual == template.render_template("main", {"Value": "done"}) == "done"


def test_linked_render_resolves_recursive_root_without_a_namespace_cycle() -> None:
    template = Template(
        '{{if .Next}}{{template "root" .Next}}{{else}}{{.Value}}{{end}}',
        name="root",
    )
    linked = link_program(template._program, template._runtime_functions)
    data = {"Next": {"Next": None, "Value": "done"}, "Value": "outer"}

    assert "root" not in linked.namespace
    assert (
        render_linked_program(
            linked,
            data,
            functions=template._runtime_functions,
        )
        == template.render(data)
        == "done"
    )


def test_linked_cost_counts_include_associated_template_calls() -> None:
    template = Template(
        '{{define "main"}}{{template "leaf" .}}{{end}}'
        '{{define "leaf"}}{{.Value}}{{end}}'
    )

    linked = link_program(template._program, template._runtime_functions)

    assert linked.linked_write_count == 1
    assert linked.template_call_count == 1


def test_linked_render_streams_to_a_caller_writer() -> None:
    template = Template("hello {{.Name}}")
    linked = link_program(template._program, template._runtime_functions)
    writer = StringIO()

    render_linked_program_to(
        linked,
        writer,
        {"Name": "Ada"},
        functions=template._runtime_functions,
    )

    assert writer.getvalue() == "hello Ada"


@pytest.mark.parametrize("stream", [False, True])
def test_linked_render_rejects_an_undefined_selected_template(stream: bool) -> None:
    template = Template("hello")
    linked = link_program(template._program, template._runtime_functions)

    with pytest.raises(TemplateExecutionError, match=r"missing.*is not defined"):
        if stream:
            render_linked_program_to(linked, StringIO(), template_name="missing")
        else:
            render_linked_program(linked, template_name="missing")


def test_linked_unary_preserves_template_execution_errors() -> None:
    failure = TemplateExecutionError("kept")

    def fail(_value: object) -> object:
        raise failure

    template = Template("{{.Value | fail}}", functions={"fail": fail})

    with pytest.raises(TemplateExecutionError) as captured:
        template.render({"Value": "x"})

    assert captured.value is failure


def test_linked_unary_translates_function_exceptions() -> None:
    failure = RuntimeError("broken")

    def fail(_value: object) -> object:
        raise failure

    template = Template("{{.Value | fail}}", functions={"fail": fail})

    with pytest.raises(
        TemplateExecutionError, match="function 'fail' failed: broken"
    ) as caught:
        template.render({"Value": "x"})

    assert caught.value.__cause__ is failure


@pytest.mark.parametrize(
    ("source", "data", "expected"),
    [
        ("{{if $x := .Value}}{{$x}}{{end}}", {"Value": "yes"}, "yes"),
        ("{{with .User}}{{.Name}}{{end}}", {"User": {"Name": "Ada"}}, "Ada"),
        (
            "{{range $index, $value := .Items}}{{$index}}={{$value}};{{end}}",
            {"Items": ["a", "b"]},
            "0=a;1=b;",
        ),
    ],
)
def test_linked_control_pipelines_match_generic_binding_and_dot_semantics(
    source: str,
    data: object,
    expected: str,
) -> None:
    template = Template(source)

    generic = sync_vm.render_program(
        template._program,
        data,
        functions=template._runtime_functions,
        _namespace=template._namespace,
    )

    assert template.render(data) == generic == expected


def test_linked_control_pipeline_preserves_missing_key_error_location() -> None:
    template = Template("{{if .Missing}}yes{{end}}", missing_key="error")

    with pytest.raises(TemplateExecutionError) as generic:
        sync_vm.render_program(
            template._program,
            {},
            functions=template._runtime_functions,
            missing_key="error",
            _namespace=template._namespace,
        )
    with pytest.raises(TemplateExecutionError) as linked:
        template.render({})

    assert str(linked.value) == str(generic.value)
