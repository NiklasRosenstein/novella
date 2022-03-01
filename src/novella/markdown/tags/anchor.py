
from __future__ import annotations

import logging
import re
import typing as t
from pathlib import Path
from novella.build import BuildContext

from novella.markdown.preprocessor import MarkdownFile, MarkdownFiles, MarkdownPreprocessor

if t.TYPE_CHECKING:
  from novella.markdown.flavor import MarkdownFlavor, MkDocsFlavor
  from novella.markdown.tagparser import Tag

logger = logging.getLogger(__name__)


class Anchor(t.NamedTuple):
  #: The globally unique identifier of the anchor across all markdown files.
  id: str

  #: The text to display when the anchor is referenced. This is set to the `text` option that can be
  #: passed to the `@anchor` tag.
  text: str | None

  #: The header leve of the Markdown header that follows immediately after the anchor.
  header_level: int | None

  #: The text of the Markdown header that follows immediately after the anchor.
  header_text: str | None

  #: The file in which the anchor was encountered. This is relative path, relative to the temporary build
  #: directory. The #Flavor may need to explicitly understand if the content directory differs from the
  #: build root directory to construct valid URLs.
  file: Path


class AnchorTagProcessor(MarkdownPreprocessor):
  """ Implements the `@anchor` and `{@link}` tags. """

  #: The flavor of Markdown to use. Defaults to #MkDocsFlavor.
  flavor: MarkdownFlavor

  #: When this is enabled, HTML elements will always be rendered for `@anchor` tags. Otherwise, anchors
  #: that precede a Markdown header element will link to the slugified ID of that header instead.
  always_render_anchor_elements: bool = True

  def __post_init__(self) -> None:
    from novella.markdown.flavor import MkDocsFlavor
    self.flavor = MkDocsFlavor()

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import replace_tags, parse_block_tags, parse_inline_tags

    # Replace anchor tags and build the anchor index.
    self._anchor_index: dict[str, Anchor] = {}
    for file in files:
      tags = [t for t in parse_block_tags(file.content) if t.name == 'anchor']
      file.content = replace_tags(file.content, tags, lambda t: self._replace_anchor(file, t))

    # Replace link tags.
    for file in files:
      tags = [t for t in parse_inline_tags(file.content) if t.name == 'link']
      file.content = replace_tags(file.content, tags, lambda t: self._replace_link(files.build, file, t))

  def _replace_anchor(self, file: MarkdownFile, tag: Tag) -> str | None:
    # Find the next Markdown header that immediately follows the tag.
    pattern = re.compile(r'\s*(#+)(.*)(?:\n|$)', re.M)
    match = pattern.match(file.content, tag.offset_span[1])
    header_level = len(match.group(1)) if match else None
    header_text = match.group(2).strip() if match else None

    anchor = Anchor(tag.args.strip(), tag.options.get('text', None), header_level, header_text, file.path)

    if anchor.id in self._anchor_index:
      logger.warning(
        '  <fg=cyan;attr=italic>@anchor %s</fg> in <fg=yellow>%s</fg> conflicts with same anchor in '
        '  <fg=yellow>%s</fg>',
        tag.args, file.path, self._anchor_index[anchor.id].file,
      )
    else:
      self._anchor_index[anchor.id] = anchor

    if self.always_render_anchor_elements or not anchor.header_text:
      return self.flavor.render_anchor(anchor.id)

    return ''

  def _replace_link(self, build: BuildContext, file: MarkdownFile, tag: Tag) -> str | None:
    anchor_id = tag.args.strip()
    anchor = self._anchor_index.get(anchor_id)
    if not anchor:
      return f'{{@link {anchor_id}}}'

    source_page = file.output_path.relative_to(build.directory / (self.action.path or ''))
    target_page = anchor.file.relative_to(self.action.context.project_directory / (self.action.path or ''))

    if source_page != target_page:
      href = self.flavor.get_link_to_page(source_page, target_page)
    else:
      href = ''
    if self.always_render_anchor_elements or not anchor.header_text:
      href += '#' + anchor.id
    else:
      assert anchor.header_level
      href += '#' + self.flavor.get_header_id(anchor.header_level, anchor.header_text)

    text = tag.options.get('text', None) or anchor.text or anchor.header_text
    assert text is not None, anchor
    return self.flavor.render_link(text, href)
