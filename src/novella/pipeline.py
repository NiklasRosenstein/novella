
import dataclasses
import typing as t

from cleo import Command
from databind.core.annotations import alias
from novella.api import Action


@dataclasses.dataclass
class Pipeline:
  """ A pipeline is just a sequence of actions that need to be run. """

  actions: t.Annotated[list[Action], alias('pipeline')]

  def get_cleo_command(self) -> Command:
    command = Command()
    command.name = "novella"
    command.description = "Execute a pipeline to build Python API documentation."
    for action in self.actions:
      action.extend_click_arguments(command)
    return command
