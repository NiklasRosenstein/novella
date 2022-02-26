
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

if t.TYPE_CHECKING:
  from novella.action import Action
  from novella.novella import NovellaContext

logger = logging.getLogger(__name__)


class BuildContext(abc.ABC):
  """ The build context is passed to actions for execution. """

  @abc.abstractproperty
  def directory(self) -> Path:
    """ The writable build directory. Actions should absolute avoid making any changes to the filesystem inside the
    #Novella.project_directory. """

  @abc.abstractmethod
  def watch(self, path: Path) -> None:
    """ Register the specified *path* to watch for changes in file or directory contents. When an action that
    supports live reloading is running, or Novella itself has reloading enabled, the pipeline will be re-executed
    (up until the point of the action that is currently running and supports live reloading, if any). """

  @abc.abstractmethod
  def is_aborted(self) -> bool:
    """ Returns `True` to indicate that the build is aborted and the action should terminate early, if possible.
    The action may raise an #ActionAborted exception to indicate that it recognized the message and aborted early. """

  @abc.abstractmethod
  def on_abort(self, callback: t.Callable[[], t.Any]) -> None:
    """ Adds a callback that is called when the build is aborted. Allows the action to respond immediately to the
    event and initiate any sequences to abort the executio early. """

  @abc.abstractmethod
  def notify(self,  action: Action, event: str, commit: t.Callable[[], t.Any] | None = None) -> None:
    """ Send a notification about an event in the build process. The main purpose of this method is to implement
    the Novella `--intercept` CLI option, allowing you to pause the execution. The *commit* function is called
    before the intercept occurs, allowing the action to commit state to disk, allowing for introspection wil the
    execution is paused (only relevant if your action operates mostly in-memory). """


class NovellaBuilder(BuildContext):
  """ Handles the execution of the Novella pipeline. """

  class Status(enum.Enum):
    PENDING = enum.auto()
    STARTING = enum.auto()
    RUNNING = enum.auto()
    STOPPED = enum.auto()

  class EventHandler(watchdog.events.FileSystemEventHandler):

    def __init__(self, builder: NovellaBuilder) -> None:
      self._builder = builder

    def on_any_event(self, event: watchdog.events.FileSystemEvent) -> None:
      builder = self._builder
      with builder._lock:
        # Prevent multiple reloads in a small timeframe.
        if builder._last_reload is not None and time.time() - builder._last_reload < 1:
          return
        if builder._status != NovellaBuilder.Status.RUNNING:
          return
        builder._last_reload = time.time()
        builder._status = NovellaBuilder.Status.STARTING
        current_action = builder._current_action

      logger.info('<fg=blue;attr=bold>Detected file changes, re-executing pipeline ...</fg>')
      if current_action and current_action.supports_reloading:
        logger.info('  Keeping <fg=blue>%s</fg> alive.', current_action.get_description())
        builder._run_actions(builder._past_actions, True)
        with builder._lock:
          builder._status = NovellaBuilder.Status.RUNNING
      elif current_action:
        current_action.abort()

  def __init__(self, context: NovellaContext, build_directory: Path | None) -> None:
    import contextlib

    self._context = context
    self._actions = context.get_actions_ordered()
    self._past_actions: list[Action] = []
    self._build_directory = build_directory
    self._current_action: Action | None = None
    self._exit_stack = contextlib.ExitStack()
    self._observer = watchdog.observers.Observer()
    self._watching_enabled = False
    self._lock = threading.Lock()
    self._last_reload: float | None = None
    self._status = NovellaBuilder.Status.PENDING

  def _create_temporary_directory(self, exit_stack: contextlib.ExitStack) -> None:
    import tempfile
    assert not self._build_directory
    assert self._status == NovellaBuilder.Status.STARTING
    tmpdir = exit_stack.enter_context(tempfile.TemporaryDirectory(prefix='novella-'))
    logger.info('Created temporary build directory <fg=yellow>%s</fg>', tmpdir)
    self._build_directory = Path(tmpdir)
    exit_stack.callback(setattr, self, '_build_directory', None)

  def _run_actions(self, actions: t.Sequence[Action], off_record: bool = False) -> Status:
    from novella.novella import PipelineError

    past_actions = [] if off_record else self._past_actions
    for action in actions:
      if not off_record:
        with self._lock:
          self._current_action = action
          logger.debug('Executing action <info>%s</info>', action.get_description())
      try:
        action.execute(self)
      except Exception as exc:
        raise PipelineError(action.name, action.callsite) from exc
      finally:
        if not off_record:
          with self._lock:
            self._current_action = None
      past_actions.append(action)

      if not off_record:
        with self._lock:
          if self._status == NovellaBuilder.Status.STARTING:
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
    self._observer.schedule(NovellaBuilder.EventHandler(self), path, recursive=True)

  def notify(self, action: Action, event: str, commit: t.Callable[[], t.Any] | None = None) -> None:
    pass

  def is_aborted(self) -> bool:
    return False

  def on_abort(self, callback: t.Callable[[], t.Any]) -> None:
    pass

  def build(self) -> None:
    with self._lock:
      if self._status != NovellaBuilder.Status.PENDING:
        raise RuntimeError('cannot restart build with same NovellaBuilder instance')
      self._status = NovellaBuilder.Status.STARTING
      assert self._past_actions == []

    with self._exit_stack:

      # Check if any action supports reloading and enable file watching.
      if any(action.supports_reloading for action in self._actions):
        self._observer = watchdog.observers.Observer()
        self._observer.start()
        self._exit_stack.callback(self._observer.join)
        self._exit_stack.callback(self._observer.stop)

      while True:
        with contextlib.ExitStack() as local_exit_stack:
          if not self._build_directory:
            self._create_temporary_directory(local_exit_stack)
          with self._lock:
            self._status = NovellaBuilder.Status.RUNNING
          if self._run_actions(self._actions, False) != NovellaBuilder.Status.STARTING:
            break  # All actions have run without interruption

  @property
  def directory(self) -> Path:  # type: ignore
    assert self._build_directory
    return self._build_directory
