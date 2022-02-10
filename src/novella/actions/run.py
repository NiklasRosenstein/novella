
import logging
from pathlib import Path
import shutil

from novella.action import Action
from novella.novella import Novella

logger = logging.getLogger(__name__)


class RunAction(Action):
  """ An action to run a command on the command-line. """

  def __init__(self) -> None:
    self.args: list[str | Path] = []

