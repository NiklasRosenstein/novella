
import abc
import logging
import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFiles, MarkdownPreprocessor

logger = logging.getLogger(__name__)


class Anchor(t.NamedTuple):
  id: str
  text: str | None
  file: Path


class Link(t.NamedTuple):
  text: str | None
  file: Path
  target: Anchor


class Flavor(abc.ABC):
  """ Flavor for rendering Markdown elements pertaining to the `@anchor` processor plugin. """

  @abc.abstractmethod
  def render_anchor(self, anchor: Anchor) -> str | None: ...

  @abc.abstractmethod
  def render_link(self, link: Link) -> str: ...


class AnchorTagProcessor(MarkdownPreprocessor):
  """ Implements the `@anchor` and `{@link}` tags. """

  flavor: Flavor | None = None

  def __init__(self) -> None:
    self._index: dict[str, Anchor] = {}

  def process_files(self, files: MarkdownFiles) -> None:
    if not self.flavor:
      logger.warning('<fg=light gray>AnchorTagProcessor.flavor</fg> is not set')

    self._build_index(files)

  def _build_index(self, files: MarkdownFiles) -> None:
    """ Finds all anchor tags in the files and builds an index. """

    from novella.markdown.tagparser import parse_block_tags

    for file in files:
      tags = list(parse_block_tags(file.content))
      print(file.path, tags)
