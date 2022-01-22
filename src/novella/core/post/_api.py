
import abc
import logging
from pathlib import Path

from databind.core.annotations import union

from .. import Context

logger = logging.getLogger(__name__)


@union(
  union.Subtypes.entrypoint('novella.core.post.MarkdownProcessor'),
  style=union.Style.keyed,
)
class MarkdownProcessor(abc.ABC):

  @abc.abstractmethod
  def process_markdown(self, context: 'Context', path: Path) -> None:
    ...
