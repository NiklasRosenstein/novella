
import abc
import logging

from databind.core.annotations import union
from docspec import ApiObject
from novella.core.context import Context

logger = logging.getLogger(__name__)


@union(
  union.Subtypes.entrypoint('novella.core.renderer.python_api.PythonApiRenderer'),
  style=union.Style.flat,
)
class PythonApiRenderer(abc.ABC):
  """ Interface for rendering a Python API object as Markdown. """

  @abc.abstractmethod
  def init(self, context: Context) -> None:
    ...

  @abc.abstractmethod
  def render_as_markdown(self, obj: ApiObject) -> str:
    ...
