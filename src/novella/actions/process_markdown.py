
import dataclasses
import logging

from novella.context import Context
from novella.api import Action, MarkdownProcessor
from novella.util import recurse_directory

logger = logging.getLogger(__name__)


def _get_default_processors() -> list[MarkdownProcessor]:
  import databind.json
  return databind.json.load([ {"cat": {}}, {"pydoc": {}} ], list[MarkdownProcessor])


@dataclasses.dataclass
class ProcessMarkdownAction(Action):
  """ An action to process all Markdown files in the given directory with a given list of processor plugins. """

  #: The path to the directory that contains the Markdown files to be preprocessed.
  directory: str

  #: The plugins that will be used to process the Markdown files in order.
  processors: list[MarkdownProcessor] = dataclasses.field(default_factory=_get_default_processors)

  def execute(self, context: 'Context') -> None:
    for path in recurse_directory(context.build_directory / self.directory):
      if path.suffix == '.md':
        logger.info('Process %s', path)
        for plugin in self.processors:
          plugin.process_markdown(context, path)
