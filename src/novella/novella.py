
from __future__ import annotations

import argparse
import logging
import typing as t
from pathlib import Path

from .action import Action

if t.TYPE_CHECKING:
  from nr.util.inspect import Callsite
  from novella.template import Template

logger = logging.getLogger(__name__)


class Novella:
  """ This is the main class that controls the build environment and pipeline execution. """

  def __init__(self, project_directory: Path, build_directory: Path | None) -> None:
    self.project_directory = project_directory
    self._build_directory = build_directory
    self._pipeline: list[Action] = []
    self._actions: dict[str, Action] = {}
    self._option_names: list[str] = []
    self._argparser = argparse.ArgumentParser()

  @property
  def build_directory(self) -> Path:
    """ Returns the build directory. Can only be used inside #Novella.run(). """

    assert self._build_directory
    return self._build_directory

  def add_action(
    self,
    action: Action,
    name: str | None = None,
    before: str | None = None,
    after: str | None = None,
  ) -> None:
    """ Add an action to the pipeline. """

    if name in self._actions:
      raise ValueError(f'action name {name!r} already used')
    if before is not None and after is not None:
      raise ValueError('arguments "before" and "after" cannot be given at the same time')

    if before is not None:
      index = self._pipeline.index(self._actions[before])
    elif after is not None:
      index = self._pipeline.index(self._actions[after]) + 1
    else:
      index = len(self._pipeline)

    self._pipeline.insert(index, action)
    action.novella = self
    if name is not None:
      self._actions[name] = action

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

      for action in self._pipeline:
        logger.info('Executing action <info>%s</info>', action.get_description())
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

  def do(
    self,
    action_name: str,
    closure: t.Callable | None = None,
    name: str | None = None,
    before: str | None = None,
    after: str | None = None,
  ) -> None:
    """ Add an action to the Novella pipeline identified by the specified *action_name*. The action will be
    configured once it is created using the *closure*. """

    from nr.util.inspect import get_callsite
    from nr.util.plugins import load_entrypoint

    callsite = get_callsite()
    action_cls = load_entrypoint('novella.actions', action_name)
    action = _LazyAction(self.novella, action_name, action_cls, closure, callsite)
    self.novella.add_action(action, name, before, after)

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

  def __str__(self) -> str:
    return self.action_name

  def _get_action(self) -> Action:
    if self._action is None:
      self._action = self.action_cls()
      self._action.novella = self.novella
      if self.closure:
        self.closure(self._action)
    return self._action

  def get_name(self) -> str:
    inner_name = self._get_action().get_description()
    if inner_name:
      return f'{self.action_name} ({inner_name})'
    return self.action_name

  def execute(self) -> None:
    action = self._get_action()
    try:
      action.execute()
    except Exception as exc:
      raise PipelineError(self.action_name, self.callsite) from exc


class PipelineError(Exception):

  def __init__(self, action_name: str, callsite: Callsite) -> None:
    self.action_name = action_name
    self.callsite = callsite
