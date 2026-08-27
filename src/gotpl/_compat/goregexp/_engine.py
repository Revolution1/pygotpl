# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Pure Python ordered-NFA execution for the translated RE2 syntax subset."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import _parser
from . import _parser as _constants

_IGNORE_CASE = _constants.SRE_FLAG_IGNORECASE
_MULTILINE = _constants.SRE_FLAG_MULTILINE
_DOT_ALL = _constants.SRE_FLAG_DOTALL
_ASCII = _constants.SRE_FLAG_ASCII


@dataclass(slots=True)
class _Instruction:
    operation: str
    argument: object = None
    out: int | None = None
    out1: int | None = None


@dataclass(frozen=True, slots=True)
class _Fragment:
    start: int
    outs: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class _Thread:
    instruction: int
    captures: tuple[int | None, ...]


@dataclass(frozen=True, slots=True)
class LinearMatch:
    """Small Match-compatible value used by the Sprig wrapper."""

    value: str
    captures: tuple[int | None, ...]
    group_names: dict[str, int]

    def start(self) -> int:
        return self.captures[0] or 0

    def end(self) -> int:
        return self.captures[1] or 0

    def group(self, identifier: int | str = 0) -> str | None:
        group = (
            self.group_names[identifier] if isinstance(identifier, str) else identifier
        )
        beginning = self.captures[group * 2]
        end = self.captures[group * 2 + 1]
        if beginning is None or end is None:
            return None
        return self.value[beginning:end]


class LinearPattern:
    """Compiled translated pattern executed with ordered Thompson threads."""

    backend = "ordered-nfa"

    def __init__(self, pattern: str) -> None:
        parsed = _parser.parse(pattern, 0)
        self.pattern = pattern
        self._instructions: list[_Instruction] = []
        compiler = _Compiler(self._instructions)
        body = compiler.compile_sequence(parsed, int(parsed.state.flags))
        start_save = compiler.emit("save", 0)
        end_save = compiler.emit("save", 1)
        match = compiler.emit("match")
        self._instructions[start_save].out = body.start
        compiler.patch(body.outs, end_save)
        self._instructions[end_save].out = match
        self._start = start_save
        self._capture_count = int(parsed.state.groups) * 2
        self._group_names = dict(parsed.state.groupdict)

    def search(self, value: str, position: int = 0) -> LinearMatch | None:
        captures = (None,) * self._capture_count
        current: list[_Thread] = []
        candidate: tuple[int | None, ...] | None = None

        for cursor in range(position, len(value) + 1):
            if candidate is None:
                self._add_thread(current, self._start, captures, value, cursor, set())

            match_index = next(
                (
                    index
                    for index, thread in enumerate(current)
                    if self._instructions[thread.instruction].operation == "match"
                ),
                None,
            )
            if match_index is not None:
                candidate = current[match_index].captures
                del current[match_index:]
                if not current:
                    return LinearMatch(value, candidate, self._group_names)

            if cursor == len(value):
                break

            following: list[_Thread] = []
            visited: set[int] = set()
            character = value[cursor]
            for thread in current:
                instruction = self._instructions[thread.instruction]
                if instruction.operation == "rune" and _matches_rune(
                    instruction.argument, character
                ):
                    assert instruction.out is not None
                    self._add_thread(
                        following,
                        instruction.out,
                        thread.captures,
                        value,
                        cursor + 1,
                        visited,
                    )
            current = following
            if candidate is not None and not current:
                return LinearMatch(value, candidate, self._group_names)

        if candidate is None:
            return None
        return LinearMatch(value, candidate, self._group_names)

    def finditer(self, value: str) -> list[LinearMatch]:
        result: list[LinearMatch] = []
        position = 0
        while position <= len(value):
            match = self.search(value, position)
            if match is None:
                break
            result.append(match)
            position = match.end() if match.end() > match.start() else match.start() + 1
        return result

    @property
    def instruction_count(self) -> int:
        """Return the immutable compiled-program size."""
        return len(self._instructions)

    @property
    def groups(self) -> int:
        """Return the number of capturing groups excluding group zero."""
        return self._capture_count // 2 - 1

    def _add_thread(
        self,
        output: list[_Thread],
        instruction_index: int,
        captures: tuple[int | None, ...],
        value: str,
        position: int,
        visited: set[int],
    ) -> None:
        pending = [(instruction_index, captures)]
        while pending:
            index, thread_captures = pending.pop()
            if index in visited:
                continue
            visited.add(index)
            instruction = self._instructions[index]
            if instruction.operation == "jump":
                assert instruction.out is not None
                pending.append((instruction.out, thread_captures))
            elif instruction.operation == "split":
                assert instruction.out is not None and instruction.out1 is not None
                pending.append((instruction.out1, thread_captures))
                pending.append((instruction.out, thread_captures))
            elif instruction.operation == "save":
                assert isinstance(instruction.argument, int)
                updated = list(thread_captures)
                updated[instruction.argument] = position
                assert instruction.out is not None
                pending.append((instruction.out, tuple(updated)))
            elif instruction.operation == "assert":
                if _matches_assertion(instruction.argument, value, position):
                    assert instruction.out is not None
                    pending.append((instruction.out, thread_captures))
            elif instruction.operation != "fail":
                output.append(_Thread(index, thread_captures))


class AtomicPattern:
    """Linear stdlib fast path for one non-capturing consuming atom."""

    backend = "stdlib-atomic"

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self._compiled = re.compile(pattern)

    def search(self, value: str, position: int = 0) -> LinearMatch | None:
        match = self._compiled.search(value, position)
        if match is None:
            return None
        return LinearMatch(value, (match.start(), match.end()), {})

    def finditer(self, value: str) -> list[LinearMatch]:
        return [
            LinearMatch(value, (match.start(), match.end()), {})
            for match in self._compiled.finditer(value)
        ]


def compile_pattern(pattern: str) -> AtomicPattern | LinearPattern:
    """Select the proven atomic stdlib path or the general ordered NFA."""

    parsed = _parser.parse(pattern, 0)
    if _is_atomic_linear(parsed):
        return AtomicPattern(pattern)
    return LinearPattern(pattern)


class _Compiler:
    def __init__(self, instructions: list[_Instruction]) -> None:
        self.instructions = instructions

    def emit(self, operation: str, argument: object = None) -> int:
        self.instructions.append(_Instruction(operation, argument))
        return len(self.instructions) - 1

    def patch(self, outs: tuple[tuple[int, int], ...], target: int) -> None:
        for index, field in outs:
            if field == 0:
                self.instructions[index].out = target
            else:
                self.instructions[index].out1 = target

    def compile_sequence(self, sequence: Any, flags: int) -> _Fragment:
        fragments = [self.compile_operation(op, arg, flags) for op, arg in sequence]
        if not fragments:
            jump = self.emit("jump")
            return _Fragment(jump, ((jump, 0),))
        result = fragments[0]
        for fragment in fragments[1:]:
            self.patch(result.outs, fragment.start)
            result = _Fragment(result.start, fragment.outs)
        return result

    def compile_operation(
        self, operation: object, argument: Any, flags: int
    ) -> _Fragment:
        if operation is _constants.LITERAL:
            return self._rune(("literal", int(argument), flags))
        if operation is _constants.NOT_LITERAL:
            return self._rune(("not_literal", int(argument), flags))
        if operation is _constants.ANY:
            return self._rune(("any", None, flags))
        if operation is _constants.IN:
            return self._rune(("class", tuple(argument), flags))
        if operation is _constants.CATEGORY:
            return self._rune(("category", argument, flags))
        if operation is _constants.AT:
            index = self.emit("assert", (argument, flags))
            return _Fragment(index, ((index, 0),))
        if operation is _constants.SUBPATTERN:
            group, added, removed, body = argument
            nested_flags = (flags | int(added)) & ~int(removed)
            fragment = self.compile_sequence(body, nested_flags)
            if group is None:
                return fragment
            start = self.emit("save", int(group) * 2)
            end = self.emit("save", int(group) * 2 + 1)
            self.instructions[start].out = fragment.start
            self.patch(fragment.outs, end)
            return _Fragment(start, ((end, 0),))
        if operation is _constants.BRANCH:
            return self._branch(argument[1], flags)
        if operation in {_constants.MAX_REPEAT, _constants.MIN_REPEAT}:
            minimum, maximum, body = argument
            return self._repeat(
                int(minimum),
                maximum,
                body,
                flags,
                greedy=operation is _constants.MAX_REPEAT,
            )
        if operation is _constants.FAILURE or (
            operation is _constants.ASSERT_NOT and not argument[1]
        ):
            fail = self.emit("fail")
            return _Fragment(fail, ())
        raise re.error(
            f"unsupported translated regular expression operation: {operation}"
        )

    def _rune(self, argument: object) -> _Fragment:
        index = self.emit("rune", argument)
        return _Fragment(index, ((index, 0),))

    def _branch(self, branches: Any, flags: int) -> _Fragment:
        fragments = [self.compile_sequence(branch, flags) for branch in branches]
        if not fragments:
            return self.compile_sequence([], flags)
        result = fragments[-1]
        for fragment in reversed(fragments[:-1]):
            split = self.emit("split")
            self.instructions[split].out = fragment.start
            self.instructions[split].out1 = result.start
            result = _Fragment(split, fragment.outs + result.outs)
        return result

    def _repeat(
        self,
        minimum: int,
        maximum: object,
        body: Any,
        flags: int,
        *,
        greedy: bool,
    ) -> _Fragment:
        if minimum == 0 and maximum == _constants.MAXREPEAT and _nullable(body):
            fragment = self.compile_sequence(body, flags)
            loop = self.emit("split")
            if greedy:
                self.instructions[loop].out = fragment.start
                loop_exit = (loop, 1)
            else:
                self.instructions[loop].out1 = fragment.start
                loop_exit = (loop, 0)
            self.patch(fragment.outs, loop)

            optional = self.emit("split")
            if greedy:
                self.instructions[optional].out = fragment.start
                optional_exit = (optional, 1)
            else:
                self.instructions[optional].out1 = fragment.start
                optional_exit = (optional, 0)
            return _Fragment(optional, (loop_exit, optional_exit))

        result = self.compile_sequence([], flags)
        for _ in range(minimum):
            fragment = self.compile_sequence(body, flags)
            self.patch(result.outs, fragment.start)
            result = _Fragment(result.start, fragment.outs)

        unbounded = maximum == _constants.MAXREPEAT
        if unbounded:
            optional_count = 0
        else:
            assert isinstance(maximum, int)
            optional_count = maximum - minimum
        for _ in range(optional_count):
            fragment = self.compile_sequence(body, flags)
            split = self.emit("split")
            if greedy:
                self.instructions[split].out = fragment.start
                outs = (*fragment.outs, (split, 1))
            else:
                self.instructions[split].out1 = fragment.start
                outs = ((split, 0), *fragment.outs)
            self.patch(result.outs, split)
            result = _Fragment(result.start, outs)

        if unbounded:
            fragment = self.compile_sequence(body, flags)
            split = self.emit("split")
            if greedy:
                self.instructions[split].out = fragment.start
                exit_out = (split, 1)
            else:
                self.instructions[split].out1 = fragment.start
                exit_out = (split, 0)
            self.patch(fragment.outs, split)
            self.patch(result.outs, split)
            result = _Fragment(result.start, (exit_out,))
        return result


def _matches_rune(argument: object, character: str) -> bool:
    kind, value, flags = argument  # type: ignore[misc]
    flags = int(flags)
    if kind == "any":
        return bool(flags & _DOT_ALL) or character != "\n"
    codepoints = _case_variants(character, flags)
    if kind == "literal":
        return int(value) in codepoints
    if kind == "not_literal":
        return int(value) not in codepoints
    if kind == "category":
        return _matches_category(value, character, flags)
    matched = _matches_class(value, codepoints, character, flags)
    return matched


def _case_variants(character: str, flags: int) -> set[int]:
    if not flags & _IGNORE_CASE:
        return {ord(character)}
    variants = {character, character.lower(), character.upper(), character.title()}
    folded = character.casefold()
    if len(folded) == 1:
        variants.add(folded)
    if flags & _ASCII:
        variants = {
            variant for variant in variants if len(variant) == 1 and variant.isascii()
        }
    return {ord(variant) for variant in variants if len(variant) == 1}


def _matches_class(
    entries: object, codepoints: set[int], character: str, flags: int
) -> bool:
    negated = False
    matched = False
    for operation, argument in entries:  # type: ignore[union-attr]
        if operation is _constants.NEGATE:
            negated = True
        elif operation is _constants.LITERAL:
            matched = matched or int(argument) in codepoints
        elif operation is _constants.RANGE:
            beginning, end = argument
            matched = matched or any(
                int(beginning) <= code <= int(end) for code in codepoints
            )
        elif operation is _constants.CATEGORY:
            matched = matched or _matches_category(argument, character, flags)
        else:
            raise re.error(
                f"unsupported translated character class operation: {operation}"
            )
    return not matched if negated else matched


def _matches_category(category: object, character: str, flags: int) -> bool:
    ascii_mode = bool(flags & _ASCII)
    word = character.isascii() and (character.isalnum() or character == "_")
    if not ascii_mode:
        word = character.isalnum() or character == "_"
    tests = {
        _constants.CATEGORY_DIGIT: character.isdigit()
        if not ascii_mode
        else character in "0123456789",
        _constants.CATEGORY_NOT_DIGIT: not (
            character.isdigit() if not ascii_mode else character in "0123456789"
        ),
        _constants.CATEGORY_SPACE: character.isspace()
        if not ascii_mode
        else character in " \t\n\r\f\v",
        _constants.CATEGORY_NOT_SPACE: not (
            character.isspace() if not ascii_mode else character in " \t\n\r\f\v"
        ),
        _constants.CATEGORY_WORD: word,
        _constants.CATEGORY_NOT_WORD: not word,
    }
    if isinstance(category, _constants.Category) and category in tests:
        return tests[category]
    raise re.error(f"unsupported translated category: {category}")


def _matches_assertion(argument: object, value: str, position: int) -> bool:
    assertion, flags = argument  # type: ignore[misc]
    flags = int(flags)
    if assertion is _constants.AT_BEGINNING_STRING:
        return position == 0
    if assertion is _constants.AT_BEGINNING:
        return position == 0 or (
            bool(flags & _MULTILINE) and value[position - 1] == "\n"
        )
    if assertion is _constants.AT_BEGINNING_LINE:
        return position == 0 or value[position - 1] == "\n"
    if assertion is _constants.AT_END_STRING:
        return position == len(value)
    if assertion is _constants.AT_END:
        return position == len(value) or (
            bool(flags & _MULTILINE) and value[position] == "\n"
        )
    if assertion in {_constants.AT_BOUNDARY, _constants.AT_NON_BOUNDARY}:
        previous = position > 0 and _is_word(value[position - 1], flags)
        following = position < len(value) and _is_word(value[position], flags)
        boundary = previous != following
        return boundary if assertion is _constants.AT_BOUNDARY else not boundary
    raise re.error(f"unsupported translated assertion: {assertion}")


def _is_word(character: str, flags: int) -> bool:
    if flags & _ASCII and not character.isascii():
        return False
    return character.isalnum() or character == "_"


def _nullable(sequence: Any) -> bool:
    for operation, argument in sequence:
        if operation in {
            _constants.LITERAL,
            _constants.NOT_LITERAL,
            _constants.ANY,
            _constants.IN,
            _constants.CATEGORY,
            _constants.ASSERT_NOT,
        }:
            return False
        if operation is _constants.SUBPATTERN:
            if not _nullable(argument[3]):
                return False
        elif operation is _constants.BRANCH:
            if not any(_nullable(branch) for branch in argument[1]):
                return False
        elif operation in {_constants.MAX_REPEAT, _constants.MIN_REPEAT}:
            minimum, _maximum, body = argument
            if int(minimum) > 0 and not _nullable(body):
                return False
        elif operation is not _constants.AT:
            return False
    return True


def _is_atomic_linear(parsed: Any) -> bool:
    if int(parsed.state.groups) != 1 or int(parsed.state.flags) & _IGNORE_CASE:
        return False
    operations = list(parsed)
    if len(operations) != 1:
        return False
    operation, argument = operations[0]
    consuming = {
        _constants.LITERAL,
        _constants.NOT_LITERAL,
        _constants.ANY,
        _constants.IN,
        _constants.CATEGORY,
    }
    if operation in consuming:
        return True
    if operation is not _constants.MAX_REPEAT:
        return False
    _minimum, _maximum, body = argument
    body_operations = list(body)
    return len(body_operations) == 1 and body_operations[0][0] in consuming
