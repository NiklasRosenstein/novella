
import argparse
import abc
import logging
import typing as t
from pathlib import Path

from databind.core.annotations import union
from docspec import ApiObject

if t.TYPE_CHECKING:
  from novella.context import Context

logger = logging.getLogger(__name__)


@union(
  union.Subtypes.entrypoint('novella.pipeline'),
  style=union.Style.keyed,
)
class Action(abc.ABC):
  """ Actions are run as part of a pipeline. """

  @abc.abstractmethod
  def execute(self, context: 'Context') -> None: ...

  def extend_cli_parser(self, parser: argparse.ArgumentParser) -> None:
    pass

  def check_args(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    pass


@union(
  union.Subtypes.entrypoint('novella.processors.docstrings'),
  style=union.Style.keyed,
)
class DocstringProcessor(abc.ABC):
  """ Docstring processors are used by the #novella.actions.python.PythonAction to process docstrings before they
  can be inlined in Markdown source files. """

  @abc.abstractmethod
  def process_docstring(self, context: 'Context', obj: ApiObject) -> None:
    ...


@union(
  union.Subtypes.entrypoint('novella.processors.markdown'),
  style=union.Style.keyed,
)
class MarkdownProcessor(abc.ABC):
  """ Markdown processors are used by the #novella.actions.process_markdown.ProcessMarkdownAction to process Markdown
  source files in the temporary build directory. Most implementations will inherit from the
  #novella.processors.base.MarkdownTagProcessor base class to implement the inline replacement of an `@` tag like
  # `@pydoc` or `@cat`. """

  @abc.abstractmethod
  def process_markdown(self, context: 'Context', path: Path) -> None:
    ...


@union(
  union.Subtypes.entrypoint('novella.renderer.python'),
  style=union.Style.flat,
)
class PythonApiRenderer(abc.ABC):
  """ Interface for rendering a Python API object as Markdown. This is used by #novella.processors.markdown.pydoc
  to replace inline reference to Python API objects with a Markdown formatted docstring. """

  @abc.abstractmethod
  def render_as_markdown(self, context: 'Context', fqn: str, obj: ApiObject, options: list[str]) -> str:
    ...
