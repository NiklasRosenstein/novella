
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

import re
import typing as t

from nr.util.scanner import Scanner


class BlockTag(t.NamedTuple):
  name: str
  args: str
  options: dict[str, t.Any]
  line_idx: int
  end_line_idx: int


def parse_block_tags(content: str | t.Sequence[str]) -> t.Iterator[BlockTag]:
  """ Parses all tags encountered in the Markdown content. """

  if isinstance(content, str):
    content = content.splitlines()

  lines = Scanner(content)
  in_code_block = False

  for line in lines.ensure_advancing():
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
    start_lineno = lines.index

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
    else:
      lines.advance()

    # Parse TOML options after encountering the `:with` keyword.
    args, _, options_string = args.partition(':with')
    options = parse_options(options_string) if options_string else {}

    yield BlockTag(name, args, options, start_lineno, max(start_lineno, lines.index - 2))


def replace_block_tags(content: str, repl: t.Callable[[BlockTag], str | t.Iterable[str]]) -> str:
  """ Replaces all tags in *content* by the text that *repl* returns for it. """

  lines = content.splitlines()
  offset = 0
  for tag in parse_block_tags(lines[:]):
    replacement = repl(tag)
    if isinstance(replacement, str):
      replacement = [replacement]
    if replacement is None:
      continue
    lines[tag.line_idx+offset:tag.end_line_idx+1+offset] = replacement
    offset -= (tag.end_line_idx - tag.line_idx + 1) - len(replacement)
  return '\n'.join(lines)


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
