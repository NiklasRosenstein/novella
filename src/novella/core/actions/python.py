
import dataclasses
import logging

# We rely on the existing PythonLoader to avoid having to re-implement the whole logic.
from pydoc_markdown.contrib.loaders.python import PythonLoader
from pydoc_markdown import Context as _PydocMarkdownContext
from .. import Action, Context

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonAction(Action, PythonLoader):

  def execute(self, context: Context) -> None:
    self._context = _PydocMarkdownContext(context.project_directory)
    self.modules = list(self.load())
    if not self.modules:
      logger.warning('No modules loaded')
