
import argparse
import sys
from pathlib import Path

from .novella import Novella, PipelineError


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-b', '--build-directory', type=Path)
  args, unknown_args = parser.parse_known_args()

  novella = Novella(Path.cwd(), args.build_directory)
  context = novella.execute_file()

  try:
    novella.build(context, unknown_args)
  except PipelineError as exc:
    print()
    print(
      f'Uncaught exception in action "{exc.action_name}" defined at {exc.callsite.filename}:{exc.callsite.lineno}',
      file=sys.stderr,
    )
    cause = exc.__cause__
    import traceback
    traceback.print_exception(type(cause), cause, cause.__traceback__)


if __name__ == '__main__':
  main()
