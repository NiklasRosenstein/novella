

from __future__ import annotations

import abc
import logging
import shlex
import shutil
import subprocess as sp
import typing as t
from pathlib import Path

from novella.graph import Node

if t.TYPE_CHECKING:
  from nr.util.inspect import Callsite
  from novella.novella import NovellaContext
  from novella.build import BuildContext

logger = logging.getLogger(__name__)


class ActionAborted(Exception):

  def __init__(self, action: Action) -> None:
    self.action = action


class Action(Node['Action']):
  """ Base class for actions that can be embedded in a Novella pipeline. """

  ENTRYPOINT = 'novella.actions'

  #: The instance of the Novella application object that controls the pipeline and lifecycle of the build process.
  #: This is set when the action is added to the pipeline and is always available when #execute() is called.
  context: NovellaContext

  #: The callsite at which the action was created.
  callsite: Callsite

  #: Set to True to indicate that the action supports content reloading while it is running. This is
  #: relevant for actions that trigger static site generators serving content that already have automatic reloading
  #: capabilities as this will tell Novella to not kill the action and instead rerun the parts of the pipeline that
  #: came before it.
  supports_reloading: bool = False

  def __init__(self, context: NovellaContext, name: str, callsite: Callsite | None = None) -> None:
    from nr.util.inspect import get_callsite
    self.context = context
    self.name = name
    self.callsite = callsite or get_callsite()
    self.__post_init__()

  def __post_init__(self) -> None:
    pass

  def get_description(self) -> str | None:
    """ Return a short text description of the action. It may be shown while the action is running to information the
    user of what is currently happening. """

    return None

  def setup(self, build: BuildContext) -> None:
    """ Called before configuration closures when the build context is ready. """

  @abc.abstractmethod
  def execute(self, build: BuildContext) -> None:
    """ Execute the action. """


class CopyFilesAction(Action):
  """ An action to copy files from the project root to the build directory. This is usually the first step in a
  pipeline as further steps can then freely modify files in the build directory without affecting the original
  project directory.

  This action is registered as an action plugin under the name `copy-files`.
  """

  #: The list of paths, relative to the project directory, to copy to the temporary build directory.
  paths: list[str | Path]

  def __post_init__(self) -> None:
    self.paths: list[str | Path] = []

  def execute(self, build: BuildContext) -> None:
    assert isinstance(self.paths, list), self.paths
    logger.info('Copy <fg=cyan>%s</fg> to <path>%s</path>', self.paths, build.directory)

    for path in self.paths:
      assert isinstance(path, (str, Path)), repr(path)
      source = self.context.project_directory / path
      dest = build.directory / path
      build.watch(source)
      if source.is_file():
        shutil.copyfile(source, dest)
      else:
        shutil.copytree(source, dest, dirs_exist_ok=True, ignore=lambda a, b: ['.git'])


class RunAction(Action):
  """ An action to run a command on the command-line. Often times this will be the last step in a pipeline to
  kick off some external tool after all pre-processing steps are completed.

  This action is registered as an action plugin under the name `run`.
  """

  #: A list of the arguments to run. Only a single command can be run using this action.
  args: list[str | Path]

  def __post_init__(self) -> None:
    self.args = []

  def get_description(self) -> str | None:
    return '$ ' + ' '.join(map(shlex.quote, map(str, self.args)))

  def execute(self, build: BuildContext) -> None:
    assert self.args, 'no RunAction.args specified'
    logger.info('Run <fg=cyan>$ %s</fg>', ' '.join(map(lambda s: shlex.quote(str(s)),  self.args)))

    try:
      self._proc = sp.Popen(self.args, cwd=build.directory)
      build.on_abort(self._proc.terminate)
      self._proc.wait()
      if build.is_aborted():
        raise ActionAborted(self)
      if self._proc.returncode != 0:
        raise RuntimeError(f'command exited with code {self._proc.returncode}')
    except KeyboardInterrupt:
      # TODO: Indicate failure of the subprocess?
      return
