
from __future__ import annotations

import logging
import os
import shutil
import typing as t
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFile, MarkdownFiles, MarkdownPreprocessor

if t.TYPE_CHECKING:
  from novella.build import BuildContext
  from novella.markdown.tagparser import Tag

logger = logging.getLogger(__name__)


class CatTagProcessor(MarkdownPreprocessor):
  """ Replaces `@cat <filename>` tags with the contents of the referenced filename. If the filename argument
  starts with a slash, the path is considered relative to the project root directory (the one where the Novella
  build file resides in). The filename is resolved in the project directory (not the temporary build directory).

  If image references are found in the source file, they are updated to point to a path relative to the
  #content_directory if that attribute is set. If the file is not already inside that directory, it will
  be copied into an `img/` subdirectory of the #content_directory.

  __Options__

  * `slice_lines` (str) &ndash; A Python-style slice string that will slice the lines that are inserted into
    the file. Useful to strip parts of the referenced file.
  * `markdown_section` (str) &ndash; The name of a Markdown section to extract from the source file.
  * `rename_section_to` (str) &ndash; Only with *markdown_section*; rename the section to the given name.

  __Example__

      # Welcome to the Novella documentation!

      @cat ../../readme.md :with slice_lines = "2:"
  """

  content_directory: t.Optional[str] = None

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import parse_block_tags, replace_tags
    for file in files:
      tags = [t for t in parse_block_tags(file.content) if t.name == 'cat']
      file.content = replace_tags(
        file.content, tags,
        lambda t: self._replace_tag(files.context.novella.project_directory, file, files.build, t),
      )

  def _replace_tag(
    self,
    project_directory: Path,
    file: MarkdownFile,
    build: BuildContext,
    tag: Tag,
  ) -> str | None:
    """ Callback for #replace_tags().

    Arguments:
      project_directory: The project directory that contains the source files.
      file: The file that is being preprocessed.
      build: The Novella build context.
      tag: The `@cat` tag we're looking to replace.
    """

    args = tag.args.strip()
    if args.startswith('/'):
      source_path = Path(project_directory / args[1:])
    else:
      source_path = (file.source_path or file.path).parent / args

    source_path = source_path.resolve()
    build.watch(source_path)

    try:
      text = source_path.resolve().read_text()
    except FileNotFoundError:
      logger.warning('@cat unable to resolve <fg=cyan>%s</fg> in file <fg=yellow>%s</fg>', args, file.output_path)
      return None

    if 'slice_lines' in tag.options:
      # TODO (@NiklasRosenstein): This is pretty dirty; we should parse the slice ourselves.
      lines = text.splitlines()
      lines = eval(f'lines[{tag.options["slice_lines"]}]')
      text = '\n'.join(lines)

    if 'markdown_section' in tag.options:
      text = self._extract_markdown_section(text, tag.options['markdown_section'], tag.options.get('rename_section_to'))

    text = self._replace_image_references(project_directory, file.path, source_path, build, text)

    # Preprocess the content before returning it.
    text = self.action.repeat(file.path, file.output_path, text, source_path, self)

    return text

  def _replace_image_references(
    self,
    project_directory: Path,
    file_path: Path,
    source_path: Path,
    build: BuildContext,
    text: str,
  ) -> str:
    """
    Arguments:
      project_directory: The project directory that contains the source files.
      file_path: The path to the file that we're preprocessing.
      source_path: The path to the file that we're cat-ing into the *file_path*.
      build: The Novella build context.
      text: The text to preprocess.
    """

    import re
    from nr.util.fs import is_relative_to

    assert self.action.path
    rel_content_directory = Path(self.content_directory or self.action.path)
    content_directory = project_directory / rel_content_directory

    def _sub(match: re.Match) -> str:
      path: str = match.group(2)
      full_path = project_directory / source_path.parent / path
      if not full_path.exists():
        logger.warning('Image file <fg=yellow>%s</fg> referenced in <fg=yellow>%s</fg> not found', full_path, source_path)
        return match.group(0)
      build.watch(full_path)
      if not is_relative_to(full_path, content_directory):
        relative_path = str(Path('img', full_path.name))
        target_path = build.directory / rel_content_directory / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(full_path, target_path)
      else:
        relative_path = str(full_path.relative_to(content_directory))

      relative_path = relative_path.replace(os.sep, '/')
      if file_path.name != 'index.md':
        relative_path = '../' + relative_path

      return match.group(1) + str(relative_path) + match.group(3)

    text = re.sub(r'(!\[[^\]]*?\]\()([^\)]+?)(\))', _sub, text)
    text = re.sub(r'(<img.*?src=")([^"]+?)(".*?/?>)', _sub, text)
    return text

  def _extract_markdown_section(self, markdown: str, section_name: str, rename_to: str | None) -> str:
    """ Extracts the section marked by the given *section_name* from the *markdown* code. """

    lines = markdown.splitlines()
    result = []
    level: int | None = None
    for line in lines:
      if line.startswith('#'):
        current_section = line.lstrip('#')
        current_level = len(line) - len(current_section)
        if level is None and current_section.strip() == section_name:
          level = current_level
          if rename_to is not None:
            line = '#' * level + ' ' + rename_to
        elif level is not None and current_level <= level:
          break
      if level is not None:
        result.append(line)
    return '\n'.join(result)
