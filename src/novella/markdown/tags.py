
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


class Tag(t.NamedTuple):
  name: str
  args: str
  line_idx: int
  end_line_idx: int


def parse_tags(content: str | t.Sequence[str]) -> t.Iterator[Tag]:
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

    yield Tag(name, args, start_lineno, max(start_lineno, lines.index - 2))


def replace_tags(content: str, repl: t.Callable[[Tag], str | t.Iterable[str]]) -> str:
  """ Replaces all tags in *content* by the text that *repl* returns for it. """

  lines = content.splitlines()
  offset = 0
  for tag in parse_tags(lines[:]):
    replacement = repl(tag)
    if isinstance(replacement, str):
      replacement = [replacement]
    lines[tag.line_idx+offset:tag.end_line_idx+1+offset] = replacement
    offset -= (tag.end_line_idx - tag.line_idx + 1) - len(replacement)
  return '\n'.join(lines)
