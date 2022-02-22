
from __future__ import annotations

import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFiles, MarkdownPreprocessor
from novella.novella import Novella

if t.TYPE_CHECKING:
  from novella.markdown.tagparser import Tag


class CatTagProcessor(MarkdownPreprocessor):
  """ Replaces `@cat <filename>` tags with the contents of the referenced filename. The string `$project` may be
  used in the filename argument to reference the project directory; otherwise the path will be considered relative
  to the current file in the project directory (not the temporary build directory). """

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import parse_block_tags, replace_tags
    for file in files:
      tags = parse_block_tags(file.content)
      file.content = replace_tags(file.content, tags, lambda t: self._replace_tag(files.novella, file.path, t))

  def _replace_tag(self, novella: Novella, file_path: Path, tag: Tag) -> str | None:
    if tag.name != 'cat': return None
    # TODO (@NiklasRosenstein): Parse TOML options in block tag
    args = tag.args.strip()
    if args.startswith('/'):
      path = Path(novella.project_directory / args[1:])
    else:
      assert not file_path.is_absolute(), file_path
      path = file_path.parent / args
      path = (novella.project_directory / path)
    path = path.resolve()
    try:
      return path.resolve().read_text()
    except FileNotFoundError:
      # TODO (@NiklasRosenstein): Log a warning
      return None
