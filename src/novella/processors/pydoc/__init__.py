
import re
import logging
import typing as t
from pathlib import Path

from docspec import ApiObject, Module, visit

from novella.actions.process_markdown._novella_tag import NovellaTagProcessor
from novella.novella import Novella
from .loader import PythonLoader
from .jinja_renderer import JinjaPythonApiRenderer

logger = logging.getLogger(__name__)


class PydocProcessor(NovellaTagProcessor):
  """ Processor for `@pydoc` tags. """

  def __init__(self) -> None:
    super().__init__('pydoc', self._process_tag)
    self.loader = PythonLoader()
    self.renderer = JinjaPythonApiRenderer()
    self._modules: list[Module] | None = None

  def _process_tag(self, novella: Novella, path: Path, args: str) -> str | None:
    match = re.match(r'\s*([a-zA-Z0-9_\.]+)\s*(?:\[(.*)\])?\s*$', args)
    if not match:
      logger.warning('bad @pydoc tag args: %r', args)
      return self._tag_name + ' ' + args

    object_fqn: str = match.group(1)
    options_str: str | None = match.group(2)
    options = [x.strip() for x in options_str.split(',')] if options_str else []

    if self._modules is None:
      self._modules = self.loader.load_all(novella.project_directory)

    if not self._modules:
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
    visit(self._modules, _match(results))
    if not results:
      logger.warning('Could not resolve reference to %r', object_fqn)
      return self._tag_name + ' ' + args

    return self.renderer.render_as_markdown(novella, object_fqn, results[0], options)
