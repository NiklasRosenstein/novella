
from __future__ import annotations

import argparse
import dataclasses
import logging
import typing as t
from pathlib import Path

from novella.action import Action
from novella.build import BuildContext

if t.TYPE_CHECKING:
  from nr.util.inspect import Callsite
  from novella.graph import Graph
  from novella.template import Template

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Option:
  long_name: str | None
  short_name: str | None
  description: str | None
  flag: bool
  default: str | bool | None
  group: str | None
  metavar: str | None


class Novella:
  """ This class is the main entrypoint for starting and controlling a Novella build. """

  BUILD_FILE = Path('build.novella')

  def __init__(self, project_directory: Path) -> None:
    self.project_directory = project_directory

  def execute_file(self, file: Path | None = None) -> NovellaContext:
    """ Execute a file, allowing it to populate the Novella pipeline. """

    from craftr.dsl import Closure
    context = NovellaContext(self)
    file = file or self.BUILD_FILE
    Closure(None, None, context).run_code(file.read_text(), str(file))
    return context


class NovellaContext:
  """ The Novella context contains the action pipeline and all the data collected during the build script execution. """

  def __init__(self, novella: Novella) -> None:
    from novella.graph import Graph

    self._novella = novella
    self._init_sequence: bool = True
    self._build: BuildContext | None = None

    self._actions = Graph[Action]()
    self._delayed: list[t.Callable] = []

    self._options: dict[str, str | bool | None] | None = None
    self._option_spec: list[Option] = []
    self._option_names: list[str] = []
    self._current_option_group: str | None = None

  @property
  def graph(self) -> Graph[Action]:
    return self._actions

  @property
  def novella(self) -> Novella:
    return self._novella

  @property
  def options(self) -> dict[str, str | bool | None]:
    assert self._options is not None, 'NovellaContext.configure() must be called before .options can be used'
    return self._options

  @property
  def project_directory(self) -> Path:
    return self.novella.project_directory

  def delay(self, callable: t.Callable) -> None:
    """ Call the closure when options are available. """

    self._delayed.append(callable)

  def option(
    self,
    long_name: str,
    short_name: str | None = None,
    description: str | None = None,
    flag: bool = False,
    default: str | bool | None = None,
    metavar: str | None = None,
  ) -> None:
    """ Add an option to the Novella pipeline that can be specified on the CLI. Actions can pick up the parsed
    option values from the #options mapping. """

    if len(long_name) == 1 and not short_name:
      long_name, short_name = '', long_name

    self._option_names.append(long_name)
    self._option_spec.append(Option(
      long_name=long_name,
      short_name=short_name,
      description=description,
      flag=flag,
      default=default,
      group=self._current_option_group,
      metavar=metavar,
    ))

  def do(
    self,
    action: str | Action,
    closure: t.Callable | None = None,
    name: str | None = None,
  ) -> Action:
    """ Add an action to the Novella pipeline identified by the specified *action_type_name*. The action will be
    configured once it is created using the *closure*. """

    from nr.util.inspect import get_callsite
    from nr.util.plugins import load_entrypoint

    if isinstance(action, str):
      if name is None:
        name = action
      action_cls = load_entrypoint(Action, action)  # type: ignore
      action = action_cls(self, name, get_callsite())
    else:
      assert isinstance(action, Action)
      assert name is None or name == action.name

    self._actions.add_node(action, self._actions.last_node_added)

    if closure is not None:
      if self._init_sequence:
        self.delay(lambda: closure(action))  # type: ignore
      else:
        closure(action)

    return action

  def action(self, action_name: str, closure: t.Callable | None = None) -> Action:
    """ Access an action by its given name, and optionally apply the *closure*. """

    action = self._actions.nodes[action_name]
    if self._init_sequence and closure:
      self.delay(lambda: closure(action))  # type: ignore
    elif closure:
      closure(action)
    return action

  def template(self, template_name: str, init: t.Callable | None = None, post: t.Callable | None = None) -> None:
    """ Load a template and add it to the Novella pipeline. """

    from nr.util.plugins import load_entrypoint
    from novella.template import Template

    try:
      self._current_option_group = f'template ({template_name})'
      template_cls: type[Template] = load_entrypoint(Template, template_name)  # type: ignore
      template = template_cls(self)
      template.setup(self)
      if init:
        init(template)
      template.define_pipeline(self)
      if post:
        post(template)
    finally:
      self._current_option_group = None

  def update_argument_parser(self, parser: argparse.ArgumentParser) -> None:
    groups: dict[str, argparse._ArgumentGroup] = {}

    for option in self._option_spec:
      group_name = option.group or 'script'
      if group_name not in groups:
        groups[group_name] = parser.add_argument_group(group_name)
      group = groups[group_name]

      option_names = []
      if option.long_name:
        option_names += [f"--{option.long_name}"]
      if option.short_name:
        option_names += [f"-{option.short_name}"]

      kwargs = {} if option.flag else {'metavar': option.metavar}
      group.add_argument(
        *option_names,
        action="store_true" if option.flag else None,  # type: ignore
        help=option.description,
        default=option.default,
        **kwargs,  # type: ignore
      )

  def configure(self, build: BuildContext, args: list[str]) -> None:
    """ Parse the argument list and run the configuration for all registered actions. """

    if not self._init_sequence:
      raise RuntimeError('already configured')
    self._init_sequence = False
    self._build = build

    parser = argparse.ArgumentParser()
    self.update_argument_parser(parser)
    parsed_args = parser.parse_args(args)
    self._options = {}
    for option_name in self._option_names:
      self.options[option_name] = getattr(parsed_args, option_name.replace('-', '_'))

    for action in self._actions.nodes.values():
      action.setup(build)

    for closure in self._delayed:
      closure()
    self._delayed.clear()


class PipelineError(Exception):

  def __init__(self, action_name: str, callsite: Callsite) -> None:
    self.action_name = action_name
    self.callsite = callsite
