
import logging
import subprocess as sp
import sys
from pathlib import Path

from novella.action import Action

logger = logging.getLogger(__name__)


class RunAction(Action):
  """ An action to run a command on the command-line. """

  def __init__(self) -> None:
    self.args: list[str | Path] = []

  def get_name(self) -> str | None:
    return self.args[0] if self.args else None

  def execute(self) -> None:
    if not self.args:
      raise RuntimeError('no args specified')
    try:
      sp.check_call(self.args, cwd=self.novella.build_directory)
    except KeyboardInterrupt:
      sys.exit(1)
