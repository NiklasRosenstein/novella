
import dataclasses
import re
import logging
import typing as t
from pathlib import Path

from docspec import ApiObject, visit

from novella.actions.python import PythonAction
from novella.context import Context
from novella.api import PythonApiRenderer
from novella.render.jinja_renderer import JinjaPythonApiRenderer
from ..base import MarkdownTagProcessor

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PydocMarkdownProcessor(MarkdownTagProcessor):
  """ Replaces `@pydoc <object_fqn>` tags in Markdown files with the API documentation from the referenced object name.

  Example:

  ```md
  @pydoc novella.pipeline.Pipeline [ options ... ]
  ```

  The options are forwarded to the #renderer.
  """

  renderer: PythonApiRenderer = dataclasses.field(default_factory=JinjaPythonApiRenderer)

  def process_tag(self, context: Context, path: Path, tag_name: str, args: str) -> str | None:
    if tag_name != 'pydoc':
      return None

    match = re.match(r'\s*([a-zA-Z0-9_\.]+)\s*(?:\[(.*)\])?\s*$', args)
    if not match:
      logger.warning('bad @pydoc tag args: %r', args)
      return tag_name + args

    object_fqn: str = match.group(1)
    options_str: str | None = match.group(2)
    options = [x.strip() for x in options_str.split(',')] if options_str else []

    if not (python := context.get_action(PythonAction)):
      logger.warning('Could not find %s', object_fqn)
      return f'*Could not find `{object_fqn}`*'

    # TODO (@NiklasRosenstein): Add helper function to docspec to resolve by FQN (respecting imports).

    def _match(results: list[ApiObject]) -> t.Callable[[ApiObject], t.Any]:
      def matcher(obj: ApiObject) -> None:
        fqn = '.'.join(y.name for y in obj.path)
        if fqn == object_fqn:
          results.append(obj)
      return matcher

    results: list[ApiObject] = []
    visit(python.modules, _match(results))
    if not results:
      logger.warning('Could not resolve reference to %r', object_fqn)
      return tag_name + args

    return self.renderer.render_as_markdown(context, object_fqn, results[0], options)
