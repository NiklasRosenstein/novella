
import abc
import re
from pathlib import Path
from novella.context import Context
from novella.api import MarkdownProcessor


class MarkdownTagProcessor(MarkdownProcessor):
  """ Base class for markdown processors that understand tags starting with an "at" character. """

  def process_markdown(self, context: 'Context', path: Path) -> None:
    lines = path.read_text().splitlines()
    in_code_block = False
    for idx, line in enumerate(lines):
      if line.startswith('```'):
        in_code_block = not in_code_block
        continue
      match = re.match(r'^@([\w_\-]+)', line)
      if match:
        repl = self.process_tag(context, path, match.group(1), line[match.end():])
        if repl is not None:
          lines[idx] = repl
    path.write_text('\n'.join(lines))

  @abc.abstractmethod
  def process_tag(self, context: Context, path: Path, tag_name: str, args: str) -> str | None:
    ...
