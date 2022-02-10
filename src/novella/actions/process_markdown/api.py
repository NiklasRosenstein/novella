
from __future__ import annotations

import abc
import re
import typing as t
from pathlib import Path

from nr.util.proxy import threadlocal
from nr.util.generic import T
from nr.util.plugins import PluginRegistry

from novella.novella import Novella

# Global registry for plugins that is used by the {@link novella_tag()} decorator.
plugin_registry: PluginRegistry = threadlocal()

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
  """

  from ._novella_tag import NovellaTagProcessor

  if isinstance(arg, str):
    def decorator(func):
      plugin_registry.register(MarkdownProcessor, arg, NovellaTagProcessor(arg, func))
      return func
    return decorator
  else:
    return novella_tag(arg.__name__)(arg)
