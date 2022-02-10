
import dataclasses
import logging
import shutil
from pathlib import Path

from novella.action import Action

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class CopyFilesAction(Action):
  """ An action to copy files from the project root to the temporary build directory. """

  def __init__(self) -> None:
    self.paths: list[str | Path] = []

  def execute(self) -> None:
    assert isinstance(self.paths, list)
    logger.info('Copy %s to %s', self.paths, self.novella.build_directory)
    for path in self.paths:
      assert isinstance(path, (str, Path)), repr(path)
      source = self.novella.project_directory / path
      dest = self.novella.build_directory / path
      if source.is_file():
        shutil.copyfile(source, dest)
      else:
        shutil.copytree(source, dest, dirs_exist_ok=True)
