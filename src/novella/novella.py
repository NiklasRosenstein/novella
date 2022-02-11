
from __future__ import annotations

import argparse
from re import A
import typing as t
from pathlib import Path

from .action import Action

if t.TYPE_CHECKING:
  from nr.util.inspect import Callsite
  from novella.template import Template


class Novella:
  """ This is the main class that controls the build environment and pipeline execution. """

  def __init__(self, project_directory: Path, build_directory: Path | None) -> None:
    self.project_directory = project_directory
    self._build_directory = build_directory
    self._actions: list[Action] = []
    self._option_names: list[str] = []
    self._argparser = argparse.ArgumentParser()

  @property
  def build_directory(self) -> Path:
    """ Returns the build directory. Can only be used inside {@link Novella.run()}. """

    assert self._build_directory
    return self._build_directory

  def add_action(self, action: Action) -> None:
    """ Add an action to the pipeline. """

    self._actions.append(action)
    action.novella = self

  def build(self, context: NovellaContext, args: list[str]) -> None:
    """ Run the actions in the Novella pipeline. """

    import contextlib
    import tempfile

    parsed_args = self._argparser.parse_args(args)
    for option_name in self._option_names:
      context.options[option_name] = getattr(parsed_args, option_name.replace('-', '_'))

    with contextlib.ExitStack() as exit_stack:
      if not self._build_directory:
        self._build_directory = Path(exit_stack.enter_context(tempfile.TemporaryDirectory(prefix='novella-')))
        @exit_stack.callback
        def unset_build_directory():
          self._build_directory = None

      for action in self._actions:
        action.execute()

  def execute_file(self, file: Path = Path('build.novella')) -> NovellaContext:
    """ Execute a file, allowing it to populate the Novella pipeline. """

    from craftr.dsl import Closure
    context = NovellaContext(self)
    Closure(None, None, context).run_code(file.read_text(), str(file))
    return context


class NovellaContext:

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

    if len(long_name) == 1 and not short_name:
      long_name, short_name = '', long_name

    option_names = []
    if long_name:
      option_names += [f"--{long_name}"]
    if short_name:
      option_names += [f"-{short_name}"]

    self.novella._argparser.add_argument(
      *option_names,
      action="store_true" if flag else None,
      help=description,
      default=default
    )
    self.novella._option_names.append(long_name)

  def do(self, action_name: str, closure: t.Callable | None = None) -> None:
    """ Add an action to the Novella pipeline identified by the specified *action_name*. The action will be
    configured once it is created using the *closure*. """

    from nr.util.inspect import get_callsite
    from nr.util.plugins import load_entrypoint

    callsite = get_callsite()
    action_cls = load_entrypoint('novella.actions', action_name)
    self.novella._actions.append(_LazyAction(self.novella, action_name, action_cls, closure, callsite))

  def template(self, template_name: str, init: t.Callable | None = None, post: t.Callable | None = None) -> None:
    """ Load a template and add it to the Novella pipeline. """

    from nr.util.plugins import load_entrypoint

    template_cls: type[Template] = load_entrypoint('novella.templates', template_name)
    template = template_cls()
    if init:
      init(template)
    template.define_pipeline(self)
    if post:
      post(template)


class _LazyAction(Action):

  def __init__(
    self,
    novella: Novella,
    action_name: str,
    action_cls: type[Action],
    closure: t.Callable | None,
    callsite: Callsite,
  ) -> None:
    self.novella = novella
    self.action_name = action_name
    self.action_cls = action_cls
    self.closure = closure
    self.callsite = callsite
    self._action: Action | None = None

  def execute(self) -> None:
    action = self.action_cls()
    action.novella = self.novella
    if self.closure:
      self.closure(action)
    try:
      action.execute()
    except Exception as exc:
      raise PipelineError(self.action_name, self.callsite) from exc


class PipelineError(Exception):

  def __init__(self, action_name: str, callsite: Callsite) -> None:
    self.action_name = action_name
    self.callsite = callsite
