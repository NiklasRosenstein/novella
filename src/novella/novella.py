
from __future__ import annotations

import argparse
import dataclasses
import logging
import typing as t
from pathlib import Path

from novella.action import Action, ActionSemantics

if t.TYPE_CHECKING:
  from nr.util.inspect import Callsite
  from novella.build import Builder
  from novella.template import Template

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Option:
  long_name: str | None
  short_name: str | None
  description: str | None
  flag: bool
  default: str | bool | None


class Novella:
  """ This is the main class that controls the build environment and pipeline execution. """

  BUILD_FILE = Path('build.novella')

  def __init__(self, project_directory: Path, build_directory: Path | None) -> None:
    self.project_directory = project_directory
    self._build_directory = build_directory
    self._pipeline: list[Action] = []
    self._actions: dict[str, Action] = {}
    self._option_names: list[str] = []
    self._options: list[Option] = []
    self._enable_watching = True
    self._build: Builder | None = None

  @property
  def build(self) -> Builder:
    """ Returns the build manager. Can only be used inside #Novella.run(). """

    assert self._build is not None
    return self._build

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

  def update_argument_parser(self, parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group('script')
    for option in self._options:
      option_names = []
      if option.long_name:
        option_names += [f"--{option.long_name}"]
      if option.short_name:
        option_names += [f"-{option.short_name}"]
      group.add_argument(
        *option_names,
        action="store_true" if option.flag else None,
        help=option.description,
        default=option.default
      )

  def run_build(self, context: NovellaContext, args: list[str]) -> None:
    """ Execute the Novella pipeline. """

    from .build import DefaultBuilder

    parser = argparse.ArgumentParser()
    self.update_argument_parser(parser)
    parsed_args = parser.parse_args(args)
    for option_name in self._option_names:
      context.options[option_name] = getattr(parsed_args, option_name.replace('-', '_'))

    try:
      self._build = DefaultBuilder(self._pipeline, self._build_directory)
      if self._enable_watching:
        self._build.enable_watching()
      self._build.run()
    finally:
      self._build = None

  def execute_file(self, file: Path | None = None) -> NovellaContext:
    """ Execute a file, allowing it to populate the Novella pipeline. """

    from craftr.dsl import Closure
    context = NovellaContext(self)
    Closure(None, None, context).run_code((file or self.BUILD_FILE).read_text(), str(file))
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
    return self.novella.build.directory

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

    self.novella._option_names.append(long_name)
    self.novella._options.append(Option(long_name, short_name, description, flag, default))

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
    action_cls = load_entrypoint(Action, action_name)
    action = _LazyAction(self.novella, action_name, action_cls, closure, callsite)
    self.novella.add_action(action, name, before, after)

  def template(self, template_name: str, init: t.Callable | None = None, post: t.Callable | None = None) -> None:
    """ Load a template and add it to the Novella pipeline. """

    from nr.util.plugins import load_entrypoint
    from novella.template import Template

    template_cls: type[Template] = load_entrypoint(Template, template_name)
    template = template_cls()
    if init:
      init(template)
    template.define_pipeline(self)
    if post:
      post(template)

  def enable_file_watching(self) -> None:
    self.novella._enable_watching = True


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

  def __repr__(self) -> str:
    return f'_LazyAction({self.action_name!r})'

  def __str__(self) -> str:
    return self.action_name

  def _get_action(self) -> Action:
    if self._action is None:
      self._action = self.action_cls()
      self._action.novella = self.novella
      if self.closure:
        self.closure(self._action)
    return self._action

  def get_description(self) -> str | None:
    inner_name = self._get_action().get_description()
    if inner_name:
      return f'{self.action_name} ({inner_name})'
    return self.action_name

  def get_semantic_flags(self) -> ActionSemantics:
    return self._get_action().get_semantic_flags()

  def execute(self) -> None:
    action = self._get_action()
    try:
      action.execute()
    except Exception as exc:
      raise PipelineError(self.action_name, self.callsite) from exc

  def abort(self) -> None:
    return self._get_action().abort()


class PipelineError(Exception):

  def __init__(self, action_name: str, callsite: Callsite) -> None:
    self.action_name = action_name
    self.callsite = callsite
