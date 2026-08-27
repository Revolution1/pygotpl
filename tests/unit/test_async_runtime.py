import asyncio
from collections.abc import Generator
from contextvars import ContextVar
from io import StringIO
from typing import Any

import pytest

import gotpl


@pytest.mark.asyncio
async def test_async_render_mixes_sync_and_coroutine_pipeline_functions() -> None:
    async def upper(value: object) -> str:
        await asyncio.sleep(0)
        return str(value).upper()

    def surround(value: object) -> str:
        return f"<{value}>"

    template = gotpl.Template(
        "{{upper . | surround}}",
        functions={"upper": upper, "surround": surround},
    )

    assert await template.render_async("value") == "<VALUE>"


@pytest.mark.asyncio
async def test_awaitables_feed_actions_conditions_with_and_ranges() -> None:
    async def result(value: object) -> object:
        await asyncio.sleep(0)
        return value

    template = gotpl.Template(
        "{{result .value}}|"
        "{{if result .enabled}}yes{{else}}no{{end}}|"
        "{{with result .nested}}{{.name}}{{end}}|"
        "{{range result .items}}{{.}}{{else}}empty{{end}}",
        functions={"result": result},
    )

    output = await template.render_async(
        {
            "value": "action",
            "enabled": True,
            "nested": {"name": "with"},
            "items": ["a", "b"],
        }
    )

    assert output == "action|yes|with|ab"


@pytest.mark.asyncio
async def test_sync_function_may_return_a_custom_awaitable() -> None:
    class Immediate:
        def __init__(self, value: object) -> None:
            self.value = value

        def __await__(self) -> Generator[None, None, object]:
            if False:
                yield
            return self.value

    assert (
        await gotpl.render_async("{{later .}}", "ready", functions={"later": Immediate})
        == "ready"
    )


@pytest.mark.asyncio
async def test_async_methods_and_call_builtin_await_results() -> None:
    class Service:
        async def Prefix(self) -> "Service":
            await asyncio.sleep(0)
            return self

        async def Value(self, suffix: object = "") -> str:
            await asyncio.sleep(0)
            return f"method{suffix}"

    async def function(value: object) -> str:
        return f"call:{value}"

    template = gotpl.Template(
        '{{.Prefix.Value}}|{{.Value "!"}}|{{call .function "value"}}'
    )

    assert (
        await template.render_async(
            {"Prefix": Service().Prefix, "Value": Service().Value, "function": function}
        )
        == "method|method!|call:value"
    )


@pytest.mark.asyncio
async def test_async_logical_builtins_preserve_short_circuiting() -> None:
    calls: list[str] = []

    async def value(name: str, result: bool) -> bool:
        calls.append(name)
        return result

    template = gotpl.Template(
        '{{and (value "first" false) (value "skipped" true)}}|'
        '{{or (value "second" true) (value "also-skipped" false)}}',
        functions={"value": value},
    )

    assert await template.render_async() == "false|true"
    assert calls == ["first", "second"]


@pytest.mark.asyncio
async def test_async_function_result_is_unwrapped_after_awaiting() -> None:
    async def success() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.success("ok")

    async def failure() -> gotpl.FunctionResult:
        return gotpl.FunctionResult.failure(RuntimeError("failed"))

    assert (
        await gotpl.render_async("{{success}}", functions={"success": success}) == "ok"
    )
    with pytest.raises(gotpl.TemplateExecutionError, match="failed") as captured:
        await gotpl.render_async("before/{{failure}}", functions={"failure": failure})
    assert isinstance(captured.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_async_render_supports_named_templates() -> None:
    async def upper(value: object) -> str:
        return str(value).upper()

    template = gotpl.Template(
        '{{define "leaf"}}{{upper .}}{{end}}{{template "leaf" .}}',
        functions={"upper": upper},
    )

    assert await template.render_async("root") == "ROOT"
    assert await template.render_template_async("leaf", "named") == "NAMED"


@pytest.mark.asyncio
async def test_render_source_async_inherits_namespace_and_awaits_functions() -> None:
    async def identify(value: str) -> str:
        return value.upper()

    template = gotpl.Template.from_sources(
        {"helpers.tpl": '{{define "leaf"}}{{identify .}}{{end}}'},
        functions={"identify": identify},
    )

    assert (
        await template.render_source_async(
            '{{template "leaf" .}}', "dynamic", name="dynamic.tpl"
        )
        == "DYNAMIC"
    )


@pytest.mark.asyncio
async def test_async_writer_applies_backpressure_and_accepts_sync_writers() -> None:
    events: list[str] = []

    class AsyncWriter:
        async def write(self, text: str) -> int:
            events.append(f"start:{text}")
            await asyncio.sleep(0)
            events.append(f"end:{text}")
            return len(text)

    template = gotpl.Template("a{{.}}c")
    writer = AsyncWriter()
    assert await template.render_async_to(writer, "b") is None
    assert events == ["start:a", "end:a", "start:b", "end:b", "start:c", "end:c"]

    destination = StringIO()
    await template.render_async_to(destination, "b")
    assert destination.getvalue() == "abc"


@pytest.mark.asyncio
async def test_async_writer_error_preserves_partial_output() -> None:
    class FailingWriter:
        def __init__(self) -> None:
            self.output = ""

        async def write(self, text: str) -> int:
            if text == "value":
                raise OSError("destination failed")
            self.output += text
            return len(text)

    destination = FailingWriter()

    with pytest.raises(OSError, match="destination failed"):
        await gotpl.render_async_to("before/{{.}}/after", destination, "value")

    assert destination.output == "before/"


@pytest.mark.asyncio
async def test_async_writer_short_writes_are_rejected() -> None:
    class ShortWriter:
        async def write(self, text: str) -> int:
            return max(len(text) - 1, 0)

    with pytest.raises(OSError, match="short write"):
        await gotpl.render_async_to("literal", ShortWriter())


@pytest.mark.asyncio
async def test_async_errors_keep_template_source_locations() -> None:
    async def fail() -> str:
        raise RuntimeError("broken")

    template = gotpl.Template(
        'root{{define "leaf"}}before/{{fail}}{{end}}',
        name="root",
        functions={"fail": fail},
    )

    with pytest.raises(gotpl.TemplateExecutionError) as captured:
        await template.render_template_async("leaf")

    assert captured.value.source_name == "root"
    assert captured.value.template_name == "leaf"
    assert captured.value.line == 1


@pytest.mark.asyncio
async def test_cancellation_and_context_propagate_unchanged() -> None:
    marker: ContextVar[str] = ContextVar("marker", default="missing")
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def wait_for_cancellation() -> str:
        assert marker.get() == "task-context"
        started.set()
        try:
            await asyncio.Future()
        finally:
            cleaned.set()
        raise AssertionError("the cancellation fixture unexpectedly completed")

    template = gotpl.Template(
        "before/{{wait}}/after", functions={"wait": wait_for_cancellation}
    )
    token = marker.set("task-context")
    try:
        task = asyncio.create_task(template.render_async())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        marker.reset(token)

    assert cleaned.is_set()


@pytest.mark.asyncio
async def test_compiled_template_is_safe_across_concurrent_tasks() -> None:
    async def identify(value: object) -> str:
        await asyncio.sleep(0)
        return str(value)

    template = gotpl.Template("{{identify .}}", functions={"identify": identify})

    assert await asyncio.gather(*(template.render_async(i) for i in range(20))) == [
        str(i) for i in range(20)
    ]


@pytest.mark.asyncio
async def test_compiled_html_template_is_safe_across_concurrent_tasks() -> None:
    async def identify(value: object) -> str:
        await asyncio.sleep(0)
        return f"<{value}>"

    template = gotpl.HTMLTemplate(
        "<script>{{identify .}}</script>|<p>{{identify .}}</p>",
        functions={"identify": identify},
    )

    assert await asyncio.gather(
        *(template.render_async(index) for index in range(20))
    ) == [
        f'<script>"\\u003c{index}\\u003e"</script>|<p>&lt;{index}&gt;</p>'
        for index in range(20)
    ]


def test_sync_render_rejects_and_closes_coroutines() -> None:
    closed = False

    async def async_value() -> str:
        nonlocal closed
        try:
            await asyncio.sleep(0)
            return "value"
        finally:
            closed = True

    template = gotpl.Template("{{async_value}}", functions={"async_value": async_value})

    with pytest.raises(gotpl.AsyncRequiredError, match="render_async"):
        template.render()

    assert closed is False  # Closing an unstarted coroutine does not enter its body.


def test_sync_render_rejects_custom_awaitables() -> None:
    class AwaitableValue:
        def __await__(self) -> Any:
            yield

    with pytest.raises(gotpl.AsyncRequiredError, match="render_async"):
        gotpl.render("{{later}}", functions={"later": AwaitableValue})
