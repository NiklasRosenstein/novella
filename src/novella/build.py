
from __future__ import annotations

import abc
import enum
import logging
import threading
import time
import typing as t
from pathlib import Path

import watchdog.events  # type: ignore[import]
import watchdog.observers  # type: ignore[import]

from novella.action import ActionAborted  # type: ignore[import]

if t.TYPE_CHECKING:
  import contextlib
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


class _FsEventHandler(watchdog.events.FileSystemEventHandler):
  """ Re-executes the pipeline on a filesystem event. """

  def __init__(self, builder: NovellaBuilder, min_interval: float = 3) -> None:
    super().__init__()
    self.builder = builder
    self.min_interval = min_interval
    self._last_reload: float | None = None
    self._lock = threading.Lock()

  def on_any_event(self, event: watchdog.events.FileSystemEvent) -> None:
    # Enforce the minimum interval between updates.
    ctime = time.time()
    if self._last_reload and (ctime - self._last_reload) < self.min_interval:
      return
    self._last_reload = ctime

    with self.builder._cond:
      current = self.builder._current_action
      if current and current.supports_reloading:
        # Execute the pipeline in a new builder up until the given action.
        logger.info('<fg=red>Re-execute pipeline to rely on %s reloading capabilities</fg>', current.name)
        sub_builder = NovellaBuilder(
          context=self.builder._context,
          build_directory=self.builder.directory,
          stop_before_action=current.name,
          is_inner=True,
        )
        sub_builder.build()
        return
      else:
        logger.info('<fg=red>Abort current execution and restart</fg>')
        self.builder._abort()


class NovellaBuilder(BuildContext):
  """ Handles the execution of the Novella pipeline. """

  def __init__(
    self,
    context: NovellaContext,
    build_directory: Path | None,
    enable_reloading: bool = False,
    stop_before_action: str | None = None,
    is_inner: bool = False,
  ) -> None:
    self._context = context
    self._enable_reloading = enable_reloading
    self._build_directory = build_directory
    self._stop_before_action = stop_before_action
    self._is_inner = is_inner

    self._actions = list(context.graph.execution_order())
    self._current_action: Action | None = None
    self._current_action_abort: t.Callable[[], t.Any] | None = None
    self._aborted = False
    self._finished = False
    self._cond = threading.Condition(threading.RLock())
    self._observer = watchdog.observers.Observer()
    self._event_handler = _FsEventHandler(self)
    self._watched_paths: set[Path] = set()

    import contextlib
    self._exit_stack = contextlib.ExitStack()

  def _is_finished(self) -> bool:
    with self._cond:
      return self._finished

  def _create_temporary_directory(self, exit_stack: contextlib.ExitStack) -> None:
    import tempfile
    assert not self._build_directory
    tmpdir = exit_stack.enter_context(tempfile.TemporaryDirectory(prefix='novella-'))
    logger.info('Created temporary build directory <fg=yellow>%s</fg>', tmpdir)
    self._build_directory = Path(tmpdir)
    exit_stack.callback(setattr, self, '_build_directory', None)

  def _run_actions(self) -> None:
    from novella.novella import PipelineError

    for action in self._actions:

      if self._stop_before_action and action.name == self._stop_before_action:
        break

      logger.debug('Executing action <info>%s (%s)</info>', action.name, action.get_description() or '')
      with self._cond:
        self._current_action = action
        self._cond.notify_all()

      self.notify(action, 'before_execute', None)

      try:
        action.execute(self)

      # It's ok to raise this exception if the action was aborted if #is_aborted() returns True.
      except ActionAborted:
        if not self.is_aborted():
          raise

      # Any other exception is converted into a PipelineError.
      except Exception as exc:
        with self._cond:
          self._finished = True
          self._cond.notify_all()
        raise PipelineError(action.name, action.callsite) from exc

      finally:

        with self._cond:
          self._current_action = None
          self._current_action_abort = None
          self._cond.notify_all()

    # All actions passed, only if we didn't abort them.
    with self._cond:
      if not self._aborted:
        self._finished = True
        self._cond.notify_all()

  def build(self) -> None:
    import contextlib

    with contextlib.ExitStack() as exit_stack:

      # Check if any action supports reloading and enable file watching.
      if not self._is_inner and (self._enable_reloading or any(action.supports_reloading for action in self._actions)):
        logger.debug('Watching for changes in file system ...')
        self._observer.start()
        exit_stack.callback(self._observer.join)
        exit_stack.callback(self._observer.stop)

      if not self._build_directory:
        self._create_temporary_directory(exit_stack)

      while not self._is_finished():
        with self._cond:
          self._aborted = False
          self._cond.notify_all()
        self._run_actions()

  def _abort(self) -> None:
    """ Abort the current run of actions. """

    with self._cond:
      self._aborted = True
      self._cond.notify_all()
      callback, self._current_action_abort = self._current_action_abort, None

    if callback:
      callback()

  def __enter__(self) -> None:
    self._exit_stack.__enter__()
    if not self._build_directory:
      self._create_temporary_directory(self._exit_stack)

  def __exit__(self, *args) -> None:  # type: ignore
    self._exit_stack.__exit__(*args)

  # BuildContext

  @property
  def directory(self) -> Path:  # type: ignore
    assert self._build_directory
    return self._build_directory

  def watch(self, path: Path) -> None:
    """ Watch the path for changes to file contents. If any file contents change, the Novella pipeline is
    executed again (but the build script will not be reloaded). After a restart, the observer is reset. """

    path = path.resolve()
    if path not in self._watched_paths:
      self._observer.schedule(self._event_handler, path, recursive=True)
      self._watched_paths.add(path)

  def is_aborted(self) -> bool:
    with self._cond:
      return self._aborted

  def on_abort(self, callback: t.Callable[[], t.Any]) -> None:
    with self._cond:
      if self.is_aborted():
        callback()
      else:
        self._current_action_abort = callback

  def notify(self, action: Action, event: str, commit: t.Callable[[], t.Any] | None = None) -> None:
    pass
