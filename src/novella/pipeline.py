
import argparse
import dataclasses
import typing as t

from databind.core.annotations import alias
from novella.api import Action


@dataclasses.dataclass
class Pipeline:
  """ A pipeline is just a sequence of actions that need to be run. """

  actions: t.Annotated[list[Action], alias('pipeline')]

  def make_cli_parser(self,) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='novella')
    for action in self.actions:
      action.extend_cli_parser(parser)
    return parser
