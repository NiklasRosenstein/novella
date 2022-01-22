
import abc
import dataclasses
import logging
import re
import typing as t
from pathlib import Path

from databind.core.annotations import union

from .. import Action, Context

logger = logging.getLogger(__name__)


@union(
  union.Subtypes.entrypoint('novella.core._process_markdown.MarkdownProcessor'),
  style=union.Style.keyed,
)
class MarkdownProcessor(abc.ABC):

  @abc.abstractmethod
  def process_markdown(self, context: 'Context', path: Path) -> None:
    ...


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


@dataclasses.dataclass
class ProcessMarkdownAction(Action):
  """ An action to process all Markdown files in the given directory with a given list of processor plugins. """

  #: The path to the directory that contains the Markdown files to be preprocessed.
  directory: str

  #: The plugins that will be used to process the Markdown files in order.
  processors: list[MarkdownProcessor]

  def execute(self, context: 'Context') -> None:
    for path in recurse_directory(context.build_directory / self.directory):
      if path.suffix == '.md':
        logger.info('Process %s', path)
        for plugin in self.processors:
          plugin.process_markdown(context, path)


def recurse_directory(path: Path) -> t.Iterator[Path]:
  for item in path.iterdir():
    yield item
    if item.is_dir():
      yield from recurse_directory(item)
