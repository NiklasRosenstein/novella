
import re
from pathlib import Path
import typing as t

from novella.novella import Novella
from .api import MarkdownProcessor


class NovellaTagProcessor(MarkdownProcessor):

  def __init__(self, tag_name: str, func: t.Callable[[Novella, Path, str], str]) -> None:
    self._tag_name = tag_name
    self._func = func

  def process_markdown(self, novella: Novella, path: Path) -> None:
    lines = path.read_text().splitlines()
    in_code_block = False
    for idx, line in enumerate(lines):
      if line.startswith('```'):
        in_code_block = not in_code_block
        continue
      match = re.match(r'^@([\w_\-]+)', line)
      if match and match.group(1) == self._tag_name:
        repl = self._func(novella, path, line[match.end():])
        if repl is not None:
          lines[idx] = repl
    path.write_text('\n'.join(lines))
