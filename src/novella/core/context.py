
import argparse
import dataclasses
from pathlib import Path

from .pipeline import Pipeline


@dataclasses.dataclass
class Context:
  """ The pipeline context contains all the relevant information for actions that are executed as part of a pipeline.
  Actions inspect the context to find details such as the temporary build directory, the project root and search for
  other actions defined in the pipeline. """

  project_directory: Path
  build_directory: Path
  pipeline: Pipeline
  args: argparse.Namespace
