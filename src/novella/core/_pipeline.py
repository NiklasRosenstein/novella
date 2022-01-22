
import abc
import argparse
import dataclasses
import typing as t

from databind.core.annotations import alias, union

if t.TYPE_CHECKING:
  from ._context import Context


@union(
  union.Subtypes.entrypoint('novella.core._pipeline.Action'),
  style=union.Style.keyed,
)
class Action(abc.ABC):
  """ Actions are run as part of a pipeline. """

  @abc.abstractmethod
  def execute(self, context: 'Context') -> None: ...

  def extend_cli_parser(self, parser: argparse.ArgumentParser) -> None:
    pass

  def check_args(self, parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    pass


@dataclasses.dataclass
class Pipeline:
  """ A pipeline is just a sequence of actions that need to be run. """

  actions: t.Annotated[list[Action], alias('pipeline')]

  def make_cli_parser(self,) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='novella')
    for action in self.actions:
      action.extend_cli_parser(parser)
    return parser
