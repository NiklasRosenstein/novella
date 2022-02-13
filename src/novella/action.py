

from __future__ import annotations

import abc
import logging
import shlex
import shutil
import subprocess as sp
import sys
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
  from .novella import Novella

logger = logging.getLogger(__name__)


class Action(abc.ABC):
  """ Base class for actions that can be embedded in a Novella pipeline. """

  #: The instance of the Novella application object that controls the pipeline and lifecycle of the build process.
  #: This is set when the action is added to the pipeline and is always available {@meth execute()} is called.
  novella: Novella

  @abc.abstractmethod
  def execute(self) -> None:
    """ Execute the action. """

  def get_description(self) -> str | None:
    """ Return a short text description of the action. This is printed to the console when the action is executed.
    Note that actions are usually configured through {@meth NovellaContext.do()}, which wraps it in a "lazy action",
    and will prefix the action description with the action plugin name. """

    return None


class CopyFilesAction(Action):
  """ An action to copy files from the project root to the build directory. This is usually the first step in a
  pipeline as further steps can then freely modify files in the build directory without affecting the original
  project directory.

  This action is registered as an action plugin under the name `copy-files`.
  """

  #: The list of paths, relative to the project directory, to copy to the temporary build directory.
  paths: list[str | Path]

  def __init__(self) -> None:
    self.paths: list[str | Path] = []

  def execute(self) -> None:
    assert isinstance(self.paths, list)
    logger.info('  Copy <fg=cyan>%s</fg> to <path>%s</path>', self.paths, self.novella.build_directory)
    for path in self.paths:
      assert isinstance(path, (str, Path)), repr(path)
      source = self.novella.project_directory / path
      dest = self.novella.build_directory / path
      if source.is_file():
        shutil.copyfile(source, dest)
      else:
        shutil.copytree(source, dest, dirs_exist_ok=True)


class RunAction(Action):
  """ An action to run a command on the command-line. Often times this will be the last step in a pipeline to
  kick off some external tool after all pre-processing steps are completed.

  This action is registered as an action plugin under the name `run`.
  """

  #: A list of the arguments to run. Only a single command can be run using this action.
  args: list[str | Path]

  def __init__(self) -> None:
    self.args: list[str | Path] = []

  def get_description(self) -> str | None:
    return '$ ' + ' '.join(map(shlex.quote, map(str, self.args)))

  def execute(self) -> None:
    if not self.args:
      raise RuntimeError('no args specified')
    try:
      sp.check_call(self.args, cwd=self.novella.build_directory)
    except KeyboardInterrupt:
      sys.exit(1)
