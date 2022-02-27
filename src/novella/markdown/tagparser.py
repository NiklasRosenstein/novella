
""" Utilities for parsing tags in Markdown files.

A tag is an identifier preceeded by an `@` (at) character at the start of a line that is not inside a Markdown
code block. Tags are used to leave instructions for pre-processors, usually to insert content in their place.

For example, one of the built-in tags supported by the Markdown processor is the `@cat` tag which reads the
content of a file from the original project and even supports some capabilities to select only some lines from
the file.

```py
# Welcome to the documentation of my project!

@cat ../../readme.md :with { slice = "2:" }
```

The arguments for tags can encompass multiple lines if sub-sequently indented until the next blank line or a
deindentation is found.

```py
@pydoc
  novella.novella.Novella
```
"""

from __future__ import annotations

import itertools
import re
import typing as t
import typing_extensions as te


#: Function signature for replacing tags found in Markdown files. If an iterable of strings is returned,
#: the strings will be concatenated by newlines.
ReplacementFunc: te.TypeAlias = 't.Callable[[Tag], str | t.Iterable[str]]'


class Tag(t.NamedTuple):
  name: str
  args: str
  options: dict[str, t.Any]
  offset_span: tuple[int, int]
  line_span: tuple[int, int]


def parse_inline_tags(content: str) -> t.Iterator[Tag]:
  """ Parses all inline tags encountered in *content*. An inline tag starts with the sequence `{@` (curly brace open,
  at) followed by the tag name and arguments and closed with `}` (curly brace closed). The tag may span over multiple
  lines. TOML-style options can be specified in the arguments after the `:with` keyword. To encode a curly brace in
  the arguments _before_ the `:with` statement, escape it with a backslash.

  __Example__

      {@mytag arguments here \\} :with key = "value"}
  """

  from io import StringIO
  from nr.util.parsing import Scanner

  TAG_BEGIN = r'\\?\{@([\w\d_\-]+)\b'
  scanner = Scanner(content)

  def _parse_args() -> str | None:
    """ Parse until a closing curly brace is found. After encountering the `:with` keyword, opening curly braces
    must first be matched with a closing curly brace before the closing curly brace we're looking for is used. """

    args = StringIO()
    in_with = False
    braces_to_close = 1

    while scanner:

      # On encountering the `:with` keyword, we switch the parsing mode to count braces to make sure
      # we parse a full TOML string.
      if not in_with and (match := scanner.match(r'\s:with\b')):
        in_with = True
        args.write(match.group(0))
        continue

      # Match escaped closing curly braces which should be consumed
      elif not in_with and scanner.match(r'\\}'):
        args.write('}')
        continue

      # Match what appears like a new tag opening. Only allowed if escaped; otherwise the current tag
      # is considered broken.
      elif (match := scanner.match(TAG_BEGIN)):
        if match.group(0).startswith('\\'):
          args.write(match.group(0)[1:])
          continue
        else:
          # Unescaped new tag begin inside the current tag arguments.
          return None

      # Match closing curly brace, to either close a brace within the TOML options or to end the tag.
      elif scanner.char == '}':
        braces_to_close -= 1
        if braces_to_close == 0:
          scanner.next()
          break

      # Match an opening curly brace for TOML inline tables.
      elif in_with and scanner.char == '{':
        braces_to_close += 1

      args.write(scanner.char)
      scanner.next()

    # If we're at the end of the text without closing all braces, the tag is invalid.
    if braces_to_close > 0:
      return None

    return args.getvalue()

  while scanner:
    pos = scanner.pos
    match = scanner.match(TAG_BEGIN)
    if not match:
      scanner.next()
      continue

    if match.group(0).startswith('\\'):
      continue

    tag_name = match.group(1)
    args = _parse_args()
    if args is None:
      scanner.pos = pos
      scanner.seek(len(tag_name), 'cur')
      continue

    # Parse TOML options after encountering the `:with` keyword.
    args, _, options_string = args.partition(':with')
    options = parse_options(options_string) if options_string else {}

    yield Tag(
      tag_name,
      args,
      options,
      (pos.offset, scanner.pos.offset),
      (pos.line, scanner.pos.line),
    )


def parse_block_tags(content: str | t.Sequence[str]) -> t.Iterator[Tag]:
  """ Parses all block tags encountered in *content*. A block tag is a line starting with an `@` (at) symbol
  followed by the tag name and arguments, which may span over the following lines if indented. TOML-style
  options can be specified in the arguments after the `:with` keyword.

  __Example__

      @mytag arguments here
        and more arguments here
        :with
        key = "value"
    """

  from nr.util.iter import SequenceWalker

  if isinstance(content, str):
    content = content.splitlines()

  lines = SequenceWalker(content)
  in_code_block = False
  offsets = list(itertools.accumulate(map(lambda l: len(l) + 1, content)))
  offsets.insert(0, 0)

  for line in lines.safe_iter():

    if line.startswith('```'):
      in_code_block = not in_code_block
      lines.advance()
      continue

    match = re.match(r'^@([\w_\-]+)', line)
    if not match:
      lines.advance()
      continue

    name = match.group(1)
    args = line[match.end():]
    start_lineno = end_lineno = lines.index

    indent = None
    while lines.has_next() and (line := lines.next()):
      if not line.strip():
        break
      match = re.match(r'^(\s+)', line)
      if not match or (indent is not None and len(match.group(1)) < indent):
        break
      if indent is None:
        indent = len(match.group(1))
      args += '\n' + line[indent:]
      end_lineno += 1
    else:
      lines.advance()

    # Parse TOML options after encountering the `:with` keyword.
    args, _, options_string = args.partition(':with')
    options = parse_options(options_string) if options_string else {}

    yield Tag(
      name,
      args,
      options,
      (offsets[start_lineno], offsets[end_lineno+1] - 1),
      (start_lineno, end_lineno),
    )


def replace_tags(content: str, tags: t.Iterable[Tag], repl: ReplacementFunc) -> str:
  """ Replaces all inline tags in *content* by the text that *repl* returns. """

  from nr.util.text import substitute_ranges

  ranges = []
  for tag in tags:
    replacement = repl(tag)
    if replacement is None:
      continue
    if isinstance(replacement, str):
      replacement = [replacement]
    ranges.append((tag.offset_span[0], tag.offset_span[1], '\n'.join(replacement)))

  return substitute_ranges(content, ranges)


def parse_options(options: str) -> dict[str, t.Any]:
  """ Parses options formatted as TOML. Inline tables may be used without additional wrapping.

  Examples:

  * `value = "foo"` &rarr; Returns `{ "value": "foo" }`
  * `{ value1 = "foo", value = 42 }` &rarr; Returns `{ "value1": "foo", "value": 42 }`

  Normal TOML spanning multiple lines and using section names is supported as well.
  """

  import tomli
  options = options.strip()

  if options.startswith('{'):
    mapping = tomli.loads(f'a = [{options}]')
    return mapping.popitem()[1][0]
  elif options.startswith('['):
    raise ValueError('option string cannot start with `[`')
  else:
    mapping = tomli.loads(options)
    return mapping
