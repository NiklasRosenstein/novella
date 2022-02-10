
import argparse
import typing as t
from pathlib import Path

from .action import Action


class Novella:
  """ This is the main class that controls the build environment and pipeline execution. """

  def __init__(self, project_directory: Path, build_directory: Path | None) -> None:
    self.project_directory = project_directory
    self._build_directory = build_directory
    self._actions: list[Action] = []
    self._argparser = argparse.ArgumentParser()

  @property
  def build_directory(self) -> Path:
    """ Returns the build directory. Can only be used inside {@link Novella.run()}. """

    assert self._build_directory
    return self._build_directory

  def build(self) -> None:
    """ Run the actions in the Novella pipeline. """

    import contextlib
    import tempfile

    with contextlib.ExitStack() as exit_stack:
      if not self._build_directory:
        self._build_directory = Path(exit_stack.enter_context(tempfile.TemporaryDirectory(prefix='novella-')))
        @exit_stack.callback
        def unset_build_directory():
          self._build_directory = None

      for action in self._actions:
        action.execute()

  def execute_file(self, file: Path = Path('build.novella')) -> None:
    """ Execute a file, allowing it to populate the Novella pipeline. """

    from craftr.dsl import Closure
    Closure(None, None, _NovellaClosure(self)).run_code(file.read_text(), str(file))


class _NovellaClosure:

  def __init__(self, novella: Novella) -> None:
    self.novella = novella
    self.options: dict[str, str | bool | None] = {}

  @property
  def project_directory(self) -> Path:
    return self.novella.project_directory

  @property
  def build_directory(self) -> Path:
    return self.novella.build_directory

  def option(
    self,
    long_name: str,
    short_name: str | None = None,
    description: str | None = None,
    flag: bool = False,
    default: str | bool | None = None,
  ) -> None:
    """ Add an option to the Novella pipeline that can be specified on the CLI. Actions can pick up the parsed
    option values from the #options mapping. """

    option_names = [f"--{long_name}"]
    if short_name:
      option_names += [f"-{short_name}"]

    self.novella._argparser.add_argument(
      *option_names,
      action="store_true" if flag else None,
      help=description,
      default=default
    )

  def do(self, action_name: str, closure: t.Callable | None = None) -> None:
    """ Add an action to the Novella pipeline identified by the specified *action_name*. The action will be
    configured once it is created using the *closure*. """

    from nr.util.plugins import load_entrypoint
    action_cls = load_entrypoint('novella.actions', action_name)
    self.novella._actions.append(_LazyAction(self.novella, action_cls, closure))


class _LazyAction(Action):

  def __init__(self, novella: Novella, action_cls: type[Action], closure: t.Callable | None) -> None:
    self.novella = novella
    self.action_cls = action_cls
    self.closure = closure
    self._action: Action | None = None

  def execute(self) -> None:
    action = self.action_cls()
    action.novella = self.novella
    if self.closure:
      self.closure(action)
    action.execute()
