
import dataclasses
import subprocess

from . import Action, Context


@dataclasses.dataclass
class MkdocsAction(Action):
  """ An action to run Mkdocs in the temporary build directory. """

  directory: str

  def execute(self, context: 'Context') -> None:
    command = ['mkdocs', 'serve']
    subprocess.check_call(command, cwd=context.build_directory / self.directory)
