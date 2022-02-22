
from __future__ import annotations

import abc
import logging
import re
import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFile, MarkdownFiles, MarkdownPreprocessor

if t.TYPE_CHECKING:
  from novella.markdown.tagparser import Tag

logger = logging.getLogger(__name__)


class Anchor(t.NamedTuple):
  #: The globally unique identifier of the anchor across all markdown files.
  id: str

  #: The text to display when the anchor is referenced. This is set to the `text` option that can be
  #: passed to the `@anchor` tag.
  text: str | None

  #: The text of the Markdown header that follows immediately after the anchor.
  header_text: str | None

  #: The file in which the anchor was encountered. This is relative path, relative to the temporary build
  #: directory. The #Flavor may need to explicitly understand if the content directory differs from the
  #: build root directory to construct valid URLs.
  file: Path


class Link(t.NamedTuple):
  #: The ID referenced in the link.
  anchor_id: str

  #: The value of the `text` option specified to the `{@link}` tag.
  text: str | None

  #: The target anchor for this link.
  target: Anchor | None

  #: The file in which the link was encountered.
  file: Path


class AnchorAndLinkRenderer(abc.ABC):
  """ Flavor for rendering Markdown elements pertaining to the `@anchor` processor plugin. """

  @abc.abstractmethod
  def render_anchor(self, anchor: Anchor) -> str | None: ...

  @abc.abstractmethod
  def render_link(self, link: Link) -> str: ...


class AnchorTagProcessor(MarkdownPreprocessor):
  """ Implements the `@anchor` and `{@link}` tags. """

  renderer: AnchorAndLinkRenderer | None = None

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import replace_tags, parse_block_tags, parse_inline_tags

    if not self.renderer:
      logger.warning('warning: <attr=italic>AnchorTagProcessor.flavor</attr> is not set')
      return

    # Replace anchor tags and build the anchor index.
    self._anchor_index: dict[str, Anchor] = {}
    for file in files:
      file.content = replace_tags(file.content, parse_block_tags(file.content), lambda t: self._replace_anchor(file, t))

    # Replace link tags.
    for file in files:
      tags = list(parse_inline_tags(file.content))
      print(file.path, tags)
      file.content = replace_tags(file.content, tags, lambda t: self._replace_link(file, t))

  def _replace_anchor(self, file: MarkdownFile, tag: Tag) -> str | None:
    assert self.renderer

    if tag.name != 'anchor':
      return None

    # Find the next Markdown header that immediately follows the tag.
    pattern = re.compile(r'\s*#+(.*)(?:\n|$)', re.M)
    match = pattern.match(file.content, tag.offset_span[1])
    header_text = match.group(1).strip() if match else None

    anchor = Anchor(tag.args.strip(), tag.options.get('text', None), header_text, file.path)

    if anchor.id in self._anchor_index:
      logger.warning(
        '  <fg=cyan;attr=italic>@anchor %s</fg> in <fg=yellow>%s</fg> conflicts with same anchor in '
        '  <fg=yellow>%s</fg>',
        tag.args, file.path, self._anchor_index[anchor.id].file,
      )
    else:
      self._anchor_index[anchor.id] = anchor

    return self.renderer.render_anchor(anchor)

  def _replace_link(self, file: MarkdownFile, tag: Tag) -> str:
    assert self.renderer

    if tag.name != 'link':
      return None

    anchor_id = tag.args.strip()
    link = Link(anchor_id, tag.options.get('text', None), self._anchor_index.get(anchor_id), file.path)

    return self.renderer.render_link(link)
