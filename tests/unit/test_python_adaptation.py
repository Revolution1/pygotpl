from dataclasses import dataclass

import pytest

import gotpl


@dataclass
class Profile:
    name: str

    @property
    def label(self) -> str:
        return f"user:{self.name}"

    def greeting(self) -> str:
        return f"Hello, {self.name}"

    def surround(self, left: str, right: str) -> str:
        return f"{left}{self.name}{right}"


@dataclass
class Account:
    owner: Profile

    def profile(self) -> Profile:
        return self.owner


@dataclass
class Directory:
    value: Account

    def account(self) -> Account:
        return self.value


def test_dataclass_fields_and_properties_are_visible() -> None:
    assert gotpl.render("{{.name}}/{{.label}}", Profile("Ada")) == "Ada/user:Ada"


def test_mapping_keys_take_precedence_over_mapping_attributes() -> None:
    assert gotpl.render("{{.items}}", {"items": "mapped"}) == "mapped"


def test_mapping_keys_beginning_with_underscore_are_visible() -> None:
    assert gotpl.render("{{._secret}}", {"_secret": "mapped"}) == "mapped"


def test_mapping_subclass_custom_lookup_precedes_its_keys() -> None:
    class CustomMapping(dict[str, str]):
        def __gotemplate_lookup__(self, field: str) -> str:
            return f"custom:{field}"

    assert gotpl.render("{{.name}}", CustomMapping(name="mapped")) == "custom:name"


def test_private_python_attributes_are_not_visible() -> None:
    class Secret:
        _secret = "hidden"

    assert gotpl.render("{{._secret}}", Secret()) == "<no value>"


def test_property_exceptions_are_translated_and_chained() -> None:
    failure = RuntimeError("property failed")

    class Broken:
        @property
        def value(self) -> object:
            raise failure

    with pytest.raises(gotpl.TemplateExecutionError, match="property failed") as caught:
        gotpl.render("{{.value}}", Broken())

    assert caught.value.__cause__ is failure


def test_bound_methods_are_invoked_as_template_commands() -> None:
    profile = Profile("Ada")
    assert gotpl.render("{{.greeting}}", profile) == "Hello, Ada"
    assert gotpl.render('{{.surround "[" "]"}}', profile) == "[Ada]"


def test_bound_method_annotations_reject_incompatible_arguments() -> None:
    with pytest.raises(gotpl.TemplateExecutionError, match="expected str, got int"):
        gotpl.render("{{.surround 1 2}}", Profile("Ada"))


def test_no_argument_bound_methods_are_invoked_inside_field_chains() -> None:
    directory = Directory(Account(Profile("Ada")))
    assert gotpl.render("{{.account.profile.name}}", directory) == "Ada"


def test_intermediate_method_exceptions_are_translated_and_chained() -> None:
    failure = RuntimeError("chain failed")

    class Broken:
        def profile(self) -> Profile:
            raise failure

    with pytest.raises(gotpl.TemplateExecutionError, match="profile") as captured:
        gotpl.render("{{.profile.name}}", Broken())

    assert captured.value.__cause__ is failure


def test_intermediate_methods_must_accept_no_arguments() -> None:
    class Broken:
        def profile(self, name: str) -> Profile:
            return Profile(name)

    with pytest.raises(gotpl.TemplateExecutionError, match="profile"):
        gotpl.render("{{.profile.name}}", Broken())


def test_large_python_integers_remain_exact() -> None:
    value = 2**200
    assert gotpl.render("{{.}}", value) == str(value)


def test_caller_exceptions_are_translated_and_chained() -> None:
    failure = RuntimeError("caller failed")

    def fail() -> object:
        raise failure

    with pytest.raises(gotpl.TemplateExecutionError, match="caller failed") as captured:
        gotpl.render("{{fail}}", functions={"fail": fail})

    assert captured.value.__cause__ is failure


@pytest.mark.parametrize("fail_after", [0, 1])
def test_iterable_exceptions_are_translated_and_chained(fail_after: int) -> None:
    failure = RuntimeError("iterator failed")

    class BrokenIterable:
        def __iter__(self):  # type: ignore[no-untyped-def]
            if fail_after == 0:
                raise failure
            yield "first"
            raise failure

    with pytest.raises(gotpl.TemplateExecutionError, match="iterator failed") as caught:
        gotpl.render("{{range .}}{{.}}{{end}}", BrokenIterable())

    assert caught.value.__cause__ is failure


def test_iterable_template_errors_are_not_double_wrapped() -> None:
    failure = gotpl.TemplateExecutionError("iterator template failure")

    class BrokenIterable:
        def __iter__(self):  # type: ignore[no-untyped-def]
            raise failure
            yield

    with pytest.raises(gotpl.TemplateExecutionError) as caught:
        gotpl.render("{{range .}}{{end}}", BrokenIterable())

    assert caught.value is failure
    assert failure.position is not None


def test_function_values_are_truthy_but_require_call_for_invocation() -> None:
    calls: list[str] = []

    def greeting(name: str) -> str:
        calls.append(name)
        return f"hello {name}"

    data = {"function": greeting}
    assert gotpl.render("{{if .function}}set{{end}}", data) == "set"
    assert calls == []
    assert gotpl.render('{{call .function "Ada"}}', data) == "hello Ada"
    assert calls == ["Ada"]


def test_caller_functions_can_override_logical_builtin_names() -> None:
    def join(left: object, right: object) -> str:
        return f"{left}+{right}"

    template = gotpl.Template(
        '{{and "left" "right"}}',
        functions={"and": join},
    )
    assert template.render() == "left+right"
