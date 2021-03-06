
from __future__ import annotations

import logging
import os
import textwrap
import typing as t
import subprocess as sp
from pathlib import Path

from novella.markdown.preprocessor import MarkdownFiles, MarkdownPreprocessor
from novella.markdown.tagparser import parse_inline_tags

if t.TYPE_CHECKING:
  from novella.markdown.tagparser import Tag

logger = logging.getLogger(__name__)


class ShellTagProcessor(MarkdownPreprocessor):
  """ Provides a `@shell <command>` tag that runs a shell command from the project directory and inserts its output
  into the file. This is useful if parts of your documentation need to be dynamically generated by another program.

  The environment variable `BUILD_DIR` is set to point to the temporary build directory. The current working directory
  is the project directory in which the Novella build script lies.

  __Example__

      @shell cd .. && slap changelog format --all --markdown
      {@shell git describe --tag}

  !!! note The example shows how to embed a changelog generated and formatted by [Slam][].

  [Slam]: https://pypi.org/project/slap-cli/
  """

  def process_files(self, files: MarkdownFiles) -> None:
    from novella.markdown.tagparser import parse_block_tags, replace_tags
    for file in files:
      block_tags = [t for t in parse_block_tags(file.content) if t.name == 'shell']
      file.content = replace_tags(
        file.content, block_tags,
        lambda t: self._replace_tag(files.context.novella.project_directory, files.build.directory, t),
      )
      inline_tags = [t for t in parse_inline_tags(file.content) if t.name == 'shell']
      file.content = replace_tags(
        file.content, inline_tags,
        lambda t: self._replace_tag(files.context.novella.project_directory, files.build.directory, t, True),
      )

  def _replace_tag(self, project_directory: Path, build_directory: Path, tag: Tag, strip: bool = False) -> str:
    command = tag.args.strip()
    env = os.environ.copy()
    env['BUILD_DIR'] = str(build_directory)

    try:
      output = sp.check_output(command, shell=True, cwd=project_directory, env=env, stderr=sp.PIPE).decode()
    except sp.CalledProcessError as exc:
      logger.exception('@shell command <fg=cyan>%s</fg> exited with return code <fg=red>%s</fg>', command, exc.returncode)
      output = textwrap.indent((exc.stdout or b'').decode() + '' + (exc.stderr or b'').decode(), '    ')
      output = f'    $ {command}  # exited with return code {exc.returncode}\n{output}'
    else:
      prefix = tag.options.get('prefix')
      if prefix:
        output = textwrap.indent(output, str(prefix))

    return output.strip() if strip else output
