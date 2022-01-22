
import abc
import dataclasses
import typing as t

from databind.core.annotations import alias, union

if t.TYPE_CHECKING:
  from ._context import Context


@union(
  union.Subtypes.entrypoint('novella.core._config.Action'),
  style=union.Style.keyed,
)
class Action(abc.ABC):
  """ Actions are run as part of a pipeline. """

  @abc.abstractmethod
  def execute(self, context: 'Context') -> None: ...


@dataclasses.dataclass
class Pipeline:
  """ A pipeline is just a sequence of actions that need to be run. """

  actions: t.Annotated[list[Action], alias('pipeline')]
