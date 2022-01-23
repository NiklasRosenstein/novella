
import dataclasses
import typing as t
from pathlib import Path

import cleo
from .pipeline import Action, Pipeline

T_Action = t.TypeVar('T_Action', bound=Action)


@dataclasses.dataclass
class Context:
  """ The pipeline context contains all the relevant information for actions that are executed as part of a pipeline.
  Actions inspect the context to find details such as the temporary build directory, the project root and search for
  other actions defined in the pipeline. """

  project_directory: Path
  build_directory: Path
  pipeline: Pipeline
  args: cleo.Command

  def get_action(self, action_type: type[T_Action]) -> T_Action | None:
    for action in self.pipeline.actions:
      if isinstance(action, action_type):
        return action
    return None
