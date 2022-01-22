
import abc
import dataclasses
import logging
import typing as t
from pathlib import Path

from databind.core.annotations import union
from docspec import ApiObject, visit
from pydoc_markdown.contrib.processors.smart import SmartProcessor
from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer

from .. import Context
from . import MarkdownTagProcessor
from .._python import PythonAction

logger = logging.getLogger(__name__)


@union(
  union.Subtypes.entrypoint('novella.core._process_markdown._pydoc.PythonToMarkdownRenderer'),
  style=union.Style.flat,
)
class PythonToMarkdownRenderer(abc.ABC):
  """ Interface for rendering a Python API object as Markdown. """

  @abc.abstractmethod
  def render_as_markdown(self, obj: ApiObject) -> str:
    ...


@dataclasses.dataclass
class DefaultPythonToMarkdownRenderer(PythonToMarkdownRenderer):

  def render_as_markdown(self, obj: ApiObject) -> str:
    from docspec import Module
    module = Module(obj.path[-1].name, None, None, [])
    module.members.append(obj)

    SmartProcessor().process([module], None)
    renderer = MarkdownRenderer()
    return renderer.render_to_string([module])


@dataclasses.dataclass
class PydocMarkdownProcessor(MarkdownTagProcessor):
  """ Replaces `@pydoc <object_fqn>` tags in Markdown files with the API documentation from the referenced object name.

  Example:

  ```md
  @pydoc novella.core.pipeline.Pipeline
  ```
  """

  renderer: PythonToMarkdownRenderer = t.cast(t.Any, None)

  def __post_init__(self) -> None:
    if self.renderer is None:
      self.renderer = DefaultPythonToMarkdownRenderer()

  def process_tag(self, context: Context, path: Path, tag_name: str, args: str) -> str | None:
    if tag_name != 'pydoc':
      return None

    # TODO (@NiklasRosenstein): Add helper function to docspec to resolve by FQN (respecting imports).

    object_fqn = args.strip()
    def _match(results: list[ApiObject]) -> t.Callable[[ApiObject], t.Any]:
      def matcher(obj: ApiObject) -> None:
        fqn = '.'.join(y.name for y in obj.path)
        if fqn == object_fqn:
          results.append(obj)
      return matcher

    for action in context.pipeline.actions:
      if isinstance(action, PythonAction):
        results: list[ApiObject] = []
        visit(action.modules, _match(results))
        if results:
          break
    else:
      logger.warning('Could not find %s', object_fqn)
      return f'*Could not find `{object_fqn}`*'

    return self.renderer.render_as_markdown(results[0])
