
import dataclasses
import logging
import shutil

from novella.api import Action
from novella.context import Context

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CopyFilesAction(Action):
  """ An action to copy files from the project root to the temporary build directory. """

  #: The name of the file or directory relative to the project directory to copy into the build directory.
  source: str

  def execute(self, context: 'Context') -> None:
    logger.info('Copy %s to %s', self.source, context.build_directory / self.source)
    shutil.copytree(context.project_directory / self.source, context.build_directory / self.source, dirs_exist_ok=True)
