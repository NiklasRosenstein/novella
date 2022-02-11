
from __future__ import annotations

import abc
import logging
import re
import sys
import typing as t
from collections import ChainMap
from pathlib import Path

from nr.util.generic import T
from nr.util.proxy import threadlocal
from nr.util.plugins import PluginRegistry

from novella.novella import Novella

# Global registry for plugins that is used by the {@link novella_tag()} decorator.
plugin_registry: PluginRegistry = threadlocal()

# Entrypoint for plugins registered by other packages.
ENTRYPOINT = 'novella.markdown_processors'


class MarkdownProcessor(abc.ABC):
  """ Interface for processing markdown files. When called, the processor is expected to read the contents of the
  file and rewrite its contents if needed. """

  @abc.abstractmethod
  def process_markdown(self, novella: Novella, file: Path) -> None:
    ...


@t.overload
def novella_tag(tag_name: str, /) -> t.Callable[[T], T]: ...

@t.overload
def novella_tag(func: T, /) -> T: ...

def novella_tag(arg):
  """ Decorator to register a custom Novella tag that is processed in Markdown files. Novella tags are lines that
  do not appear in code blocks and start with an `@` character. The decorated function must accept the following
  arguments:

  1. The #Novella instance
  2. The path to the file that is being processed
  3. A string of the arguments following the tag

  The tag name can be specified explicitly, otherwise it is derived from the function name.

  __Example__:

  ```py
  from pathlib import Path
  from novella.actions.process_markdown.api import novella_tag
  from novella.novella import Novella

  @novella_tag("my_tag")
  def process(novella: Novella, path: Path, args: str) -> str:
    return f'Hello from my_tag: {args}'
  ```

  The tag can also be used to decorated subclasses of #NovellaTagProcessor, which will be instantiated right away.
  """

  if isinstance(arg, str):
    def decorator(processor):
      original = processor
      if isinstance(processor, type):
        if not issubclass(processor, NovellaTagProcessor):
          raise TypeError('expected subclass of NovellaTagProcessor')
        processor = processor()
      else:
        processor = _DelegateTagProcessor(arg, processor)
      plugin_registry.register(MarkdownProcessor, arg, processor)
      return original
    return decorator
  else:
    return novella_tag(arg.__name__)(arg)


class NovellaTagContext(t.NamedTuple):
  """ Helper structure that contains contextual data on the current tag that is being processed. """
  novella: Novella
  path: Path
  lineno: int
  args: str


class NovellaTagProcessor(MarkdownProcessor):
  """ This class implements the detection and replacement of Novella tags in Markdown files. A Novella tag is an
  identifier that is prefixed with an `@` (at) character at the start of the line, outside of a Markdown code block.
  The content that the tag is replaced with must be implemented by a subclass in {@func replace_tag()}.

  The processor can be configured on three levels, which are parsed using {@module tomli}.

  1. Global settings should be set in the Novella pipeline definition and should be set either in the
     {@attr options} or in some other exposed configurable attribute of the processor.
  2. Per-file settings can be set using the `@tag :set option = value` syntax inside the file. The string after
     `:set` is parsed as TOML and assigned to the processor's {@attr file_options} dictionary.
  3. Per-tag settings are parsed after the string `:with` in the tag argument line, which is also parsed as TOML.
     These options are passed to the {@func replace_tag()} method.

  __Example__:

      @pydoc :set header_level = 3
      @pydoc novella.novella.Novella :with { header_level = 3 }
  """

  tag_name: str

  def __init__(self, tag_name: str | None = None) -> None:
    if tag_name is not None:
      self.tag_name = tag_name
    if not self.tag_name:
      raise ValueError(f'{type(self).__name__}.tag_name is not set')
    self._current: NovellaTagContext | None = None
    self._logger = logging.getLogger(f'{type(self).__module__}.{type(self).__name__}')
    self.options: dict[str, t.Any] = {}
    self.file_options: dict[str, t.Any] = {}

  @property
  def current(self) -> NovellaTagContext:
    """ Returns the context for the tag that is currently being processed. Can only be accessed during processing. """
    if self._current is None:
      raise RuntimeError(f'{type(self).__name__}.current can only be accessed during processing')
    return self._current

  def log(self, level: str | int, msg: str, *args, exc: bool = False) -> None:
    """ Helper function to log a message including the path and line number of the current tag. """
    if isinstance(level, str):
      level: int = getattr(logging, level.upper())
    exc_info = sys.exc_info() if exc else None
    self._logger.log(level, '%s:%s — ' + msg, self.current.path, self.current.lineno, *args, exc_info=exc_info)

  def parse_option(self, line: str) -> tuple[str, t.Any]:
    import tomli
    line = line.strip()
    if line.startswith('{'):
      mapping = tomli.loads(f'a = [{line}]')
      return mapping.popitem()[1][0]
    elif line.startswith('['):
      raise ValueError('option string cannot start with `[`')
    else:
      mapping = tomli.loads(line)
      return mapping.popitem()

  def process_markdown(self, novella: Novella, path: Path) -> None:
    self.file_options = {}

    lines = path.read_text().splitlines()
    in_code_block = False

    for idx, line in enumerate(lines):

      # We skip over code blocks.
      if line.startswith('```'):
        in_code_block = not in_code_block
        continue

      if in_code_block:
        continue

      # Check if the line looks like  atag.
      match = re.match(r'^@([\w_\-]+)', line)
      if not match or match.group(1) != self.tag_name:
        continue

      args = line[match.end():].strip()
      self._current = NovellaTagContext(novella, path, idx + 1, args)

      # Check if a :set instruction was used.
      match = re.match(r':set\b(.*)', args)
      if match:
        try:
          key, value = self.parse_option(match.group(1))
          self.file_options[key] = value
          lines[idx] = ''
          continue
        except:
          self.log('error', f'An error occurred parsing an option for @{self.tag_name}', exc=True)

      else:
        # Parse options after :with.
        args, _, options_string = args.partition(':with')
        options = self.parse_option(options_string) if options_string else {}
        replacement = self.replace_tag(args, options)
        if replacement is not None:
          lines[idx] = replacement

    path.write_text('\n'.join(lines))

  @abc.abstractmethod
  def replace_tag(self, args: str, options: dict[str, t.Any]) -> str | None:
    """ This method must be implemented by subclasses to return a replacement text for the tag. """


class _DelegateTagProcessor(NovellaTagProcessor):

  _ProcessFunc = t.Callable[[NovellaTagContext, dict[str, t.Any]], str | None]

  def __init__(self, tag_name: str, func: _ProcessFunc = None) -> None:
    super().__init__(tag_name)
    self._func = func

  def replace_tag(self, args: str, options: dict[str, t.Any]) -> str | None:
    return self._func(self.current, ChainMap(self.options, self.file_options, options))
