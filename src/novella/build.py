
from __future__ import annotations

import abc
import contextlib
import enum
import logging
import threading
import time
import typing as t
from pathlib import Path

import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

from novella.action import ActionSemantics

if t.TYPE_CHECKING:
  from .action import Action

logger = logging.getLogger(__name__)


class Builder(abc.ABC):

  directory: Path

  @abc.abstractmethod
  def __init__(self, actions: list[Action], build_directory: Path | None) -> None: ...

  @abc.abstractmethod
  def enable_watching(self) -> None: ...

  @abc.abstractmethod
  def watch(self, path: Path) -> None: ...

  @abc.abstractmethod
  def run(self) -> None: ...


class DefaultBuilder(Builder):
  """ Handles the execution of the Novella pipeline. """

  class Status(enum.Enum):
    PENDING = enum.auto()
    STARTING = enum.auto()
    RUNNING = enum.auto()
    STOPPED = enum.auto()

  class EventHandler(watchdog.events.FileSystemEventHandler):

    def __init__(self, builder: DefaultBuilder) -> None:
      self._builder = builder

    def on_any_event(self, event):
      builder = self._builder
      with builder._lock:
        # Prevent multiple reloads in a small timeframe.
        if builder._last_reload is not None and time.time() - builder._last_reload < 1:
          return
        if builder._status != DefaultBuilder.Status.RUNNING:
          return
        builder._last_reload = time.time()
        builder._status = DefaultBuilder.Status.STARTING
        current_action = builder._current_action

      logger.info('<fg=blue;attr=bold>Detected file changes, re-executing pipeline ...</fg>')
      if current_action and current_action.get_semantic_flags() & ActionSemantics.HAS_INTERNAL_RELOADER:
        logger.info('  Keeping <fg=blue>%s</fg> alive.', current_action.get_description())
        builder._run_actions(builder._past_actions, True)
        with builder._lock:
          builder._status = DefaultBuilder.Status.RUNNING
      elif current_action:
        current_action.abort()

  def __init__(self, actions: t.Sequence[Action], build_directory: Path | None) -> None:
    import contextlib

    self._actions = actions
    self._past_actions: list[Action] = []
    self._build_directory = build_directory
    self._current_action: Action | None = None
    self._exit_stack = contextlib.ExitStack()
    self._observer = watchdog.observers.Observer()
    self._watching_enabled = False
    self._lock = threading.Lock()
    self._last_reload = None
    self._status = DefaultBuilder.Status.PENDING

  def _create_temporary_directory(self, exit_stack: contextlib.ExitStack) -> None:
    import tempfile
    assert not self._build_directory
    assert self._status == DefaultBuilder.Status.STARTING
    tmpdir = exit_stack.enter_context(tempfile.TemporaryDirectory(prefix='novella-'))
    logger.info('Created temporary build directory <fg=yellow>%s</fg>', tmpdir)
    self._build_directory = Path(tmpdir)
    exit_stack.callback(setattr, self, '_build_directory', None)

  def _run_actions(self, actions: t.Sequence[Action], off_record: bool = False) -> Status:
    past_actions = [] if off_record else self._past_actions
    for action in actions:
      if not off_record:
        with self._lock:
          self._current_action = action
          logger.debug('Executing action <info>%s</info>', action.get_description())
      try:
        action.execute()
      finally:
        if not off_record:
          with self._lock:
            self._current_action = None
      past_actions.append(action)

      if not off_record:
        with self._lock:
          if self._status == DefaultBuilder.Status.STARTING:
            break  # If the status has transitioned back to STARTING, it means we want to restart.

    with self._lock:
      return self._status

  def enable_watching(self) -> None:
    """ Enables watching files for changes and restarting the build process. """

    if self._watching_enabled and self._observer.is_alive():
      return

    self._watching_enabled = True
    self._observer.start()
    self._exit_stack.callback(self._observer.join)
    self._exit_stack.callback(self._observer.stop)

  def watch(self, path: Path) -> None:
    """ Watch the path for changes to file contents. If any file contents change, the Novella pipeline is
    executed again (but the build script will not be reloaded). After a restart, the observer is reset. """

    # TODO: What's not so good right now is that on a reload, actions might call this again
    #   and append the same path again to the observer.
    self._observer.schedule(DefaultBuilder.EventHandler(self), path, recursive=True)

  def run(self) -> None:
    with self._lock:
      if self._status != DefaultBuilder.Status.PENDING:
        raise RuntimeError('cannot restart build with same DefaultBuilder instance')
      self._status = DefaultBuilder.Status.STARTING
      assert self._past_actions == []

    with self._exit_stack:
      while True:
        with contextlib.ExitStack() as local_exit_stack:
          if not self._build_directory:
            self._create_temporary_directory(local_exit_stack)
          with self._lock:
            self._status = DefaultBuilder.Status.RUNNING
          if self._run_actions(self._actions, False) != DefaultBuilder.Status.STARTING:
            break  # All actions have run without interruption

  @property
  def directory(self) -> Path:  # type: ignore
    assert self._build_directory
    return self._build_directory
