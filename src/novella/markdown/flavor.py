
import abc
import dataclasses
import os
from pathlib import Path


class MarkdownFlavor(abc.ABC):
  """ Interface to represent a Markdown flavor. """

  @abc.abstractmethod
  def get_header_id(self, header_level: int, header_text: str) -> str:
    """ Return a slugified version of the header text which is used as the HTML element ID. """

  @abc.abstractmethod
  def get_link_to_page(self, source_page: Path, target_page: Path) -> str:
    """ Return the link from *source_page* to the specified *target_page*. Both arguments are relative paths,
    relative to what is considered the "content root directory". The paths will still include the `.md` suffix
    of the files. """

  def render_anchor(self, id: str) -> str:
    """ Render an element with the given HTML ID. """

    return f'<a id="{id}"></a>'

  def render_link(self, text: str, href: str) -> str:
    """ Construct syntax for a link to *href* with the specified *text*. """

    return f'[{text}]({href})'


@dataclasses.dataclass
class MkDocsFlavor(MarkdownFlavor):
  """ Flavor for MkDocs. Requires the #markdown module to be available. """

  prefix: str = ''

  def get_header_id(self, header_level: int, header_text: str) -> str:
    from markdown.extensions.toc import slugify
    return slugify(header_text.lower(), '-')

  def get_link_to_page(self, source_page: Path, target_page: Path) -> str:
    assert not source_page.is_absolute(), source_page
    assert not target_page.is_absolute(), target_page
    if target_page.name == 'index.md':
      target_page = target_page.parent
    else:
      target_page = target_page.with_suffix('')
    url_path = str(target_page).replace(os.sep, '/')
    if url_path == os.curdir:
      url_path = ''
    return f'/{self.prefix}{url_path}'
