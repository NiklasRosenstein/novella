
from __future__ import annotations

import abc
import logging
import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFiles, MarkdownPreprocessor

if t.TYPE_CHECKING:
  from novella.markdown.tagparser import BlockTag

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
    from novella.markdown.tagparser import replace_block_tags

    if not self.flavor:
      logger.warning('warning: <attr=italic>AnchorTagProcessor.flavor</attr> is not set')
      return

    self._build_index(files)
    for file in files:
      file.content = replace_block_tags(file.content, self._replace_anchor)

  def _build_index(self, files: MarkdownFiles) -> None:
    """ Finds all anchor tags in the files and builds an index. """

    from novella.markdown.tagparser import parse_block_tags

    duplicate_anchors: dict[str, set[Path]] = {}

    for file in files:
      for tag in parse_block_tags(file.content):
        if tag.name == 'anchor':
          anchor_id = tag.args.strip()
          if anchor_id in self._index:
            duplicate_anchors.setdefault(anchor_id, set()).update(
              self._index[anchor_id].file,
              file.path,
            )
          else:
            # TODO (@NiklasRosenstein): Look for the next Markdown header to use as the anchor text
            self._index[anchor_id] = Anchor(anchor_id, tag.options.get('text', None), file.path)

  def _replace_anchor(self, tag: BlockTag) -> str | None:
    if tag.name != 'anchor':
      return None

    return 'Anchor here'
