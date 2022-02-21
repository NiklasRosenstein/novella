

from __future__ import annotations

import abc
import enum
import logging
import shlex
import shutil
import subprocess as sp
import sys
import typing as t
from functools import reduce
from pathlib import Path

if t.TYPE_CHECKING:
  from .novella import Novella

logger = logging.getLogger(__name__)


class ActionSemantics(enum.IntEnum):
  """ Flags that indicate the behaviour of an action. """

  #: No particular behaviour.
  NONE = 0

  #: The action in itself supports an automated reloading mechanism. While the action is
  #: still running, it will not be re-launched when watched files in the project directory
  #: changes and is synced to the build directory again.
  HAS_INTERNAL_RELOADER = 1


class Action(abc.ABC):
  """ Base class for actions that can be embedded in a Novella pipeline. """

  ENTRYPOINT = 'novella.actions'

  #: The instance of the Novella application object that controls the pipeline and lifecycle of the build process.
  #: This is set when the action is added to the pipeline and is always available {@meth execute()} is called.
  novella: Novella

  @abc.abstractmethod
  def execute(self) -> None:
    """ Execute the action. """

  def abort(self) -> None:
    """ Abort the action if it is currently running. Block until the action is aborted. Do nothing otherwise. """

  def get_semantic_flags(self) -> ActionSemantics:
    """ Return flags for the action to indicate its semantics. """

    return ActionSemantics.NONE

  def get_description(self) -> str | None:
    """ Return a short text description of the action. This is printed to the console when the action is executed.
    Note that actions are usually configured through {@meth NovellaContext.do()}, which wraps it in a "lazy action",
    and will prefix the action description with the action plugin name. """

    return None


class VoidAction(Action):
  """ An action that does nothing. Sometimes used as placeholders in templates to allow users to insert actions
  before or after the placeholder. """

  def execute(self) -> None:
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
    logger.info('Copy <fg=cyan>%s</fg> to <path>%s</path>', self.paths, self.novella.build.directory)
    for path in self.paths:
      assert isinstance(path, (str, Path)), repr(path)
      source = self.novella.project_directory / path
      dest = self.novella.build.directory / path
      self.novella.build.watch(source)
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
    self._flags: ActionSemantics = ActionSemantics.NONE
    self._proc: sp.Popen | None = None
    self._aborted = False

  @property
  def flags(self) -> ActionSemantics:
    return self._flags

  @flags.setter
  def flags(self, value: str | ActionSemantics) -> None:
    if isinstance(value, str):
      value = reduce(lambda a, b: a | b, (ActionSemantics[k.strip().upper()] for k in value.split('|')))
    assert isinstance(value, ActionSemantics), type(value)
    self._flags = value

  def execute(self) -> None:
    if not self.args:
      raise RuntimeError('no args specified')
    try:
      self._proc = sp.Popen(self.args, cwd=self.novella.build.directory)
      self._proc.wait()
      if self._proc.returncode != 0 and not self._aborted:
        raise RuntimeError(f'command exited with code {self._proc.returncode}')
    except KeyboardInterrupt:
      # TODO: Indicate failure of the subprocess?
      return

  def abort(self) -> None:
    if self._proc:
      self._aborted = True
      self._proc.terminate()
      self._proc.wait()

  def get_semantic_flags(self) -> ActionSemantics:
    return self._flags

  def get_description(self) -> str | None:
    return '$ ' + ' '.join(map(shlex.quote, map(str, self.args)))
