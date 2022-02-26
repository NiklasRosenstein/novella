
from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFiles, MarkdownPreprocessor

if t.TYPE_CHECKING:
  from novella.build import BuildContext
  from novella.markdown.tagparser import Tag

logger = logging.getLogger(__name__)


class CatTagProcessor(MarkdownPreprocessor):
  """ Replaces `@cat <filename>` tags with the contents of the referenced filename. If the filename argument
  starts with a slash, the path is considered relative to the project root directory (the one where the Novella
  build file resides in). The filename is resolved in the project directory (not the temporary build directory).

  __Options__

  * `slice_lines` (str) &ndash; A Python-style slice string that will slice the lines that are inserted into
    the file. Useful to strip parts of the referenced file.

  __Example__

      # Welcome to the Novella documentation!

      @cat ../../readme.md :with slice_lines = "2:"
  """

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import parse_block_tags, replace_tags
    for file in files:
      tags = parse_block_tags(file.content)
      file.content = replace_tags(
        file.content, tags,
        lambda t: self._replace_tag(files.context.novella.project_directory, file.path, files.build, t),
      )

  def _replace_tag(self, project_directory: Path, file_path: Path, build: BuildContext, tag: Tag) -> str | None:
    if tag.name != 'cat': return None
    args = tag.args.strip()
    if args.startswith('/'):
      path = Path(project_directory / args[1:])
    else:
      assert not file_path.is_absolute(), file_path
      path = file_path.parent / args
      path = (project_directory / path)

    path = path.resolve()
    build.watch(path)
    try:
      text = path.resolve().read_text()
    except FileNotFoundError:
      logger.warning('@cat unable to resolve <fg=cyan>%s</fg> in file <fg=yellow>%s</fg>', args, file_path)
      return None

    if 'slice_lines' in tag.options:
      # TODO (@NiklasRosenstein): This is pretty dirty; we should parse the slice ourselves.
      lines = text.splitlines()
      lines = eval(f'lines[{tag.options["slice_lines"]}]')
      text = '\n'.join(lines)

    return text
