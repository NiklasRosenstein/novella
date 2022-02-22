
import argparse
import logging
import sys
from pathlib import Path

from nr.util.logging.filters.simple_filter import SimpleFilter
from nr.util.logging.formatters.terminal_colors import TerminalColorFormatter

from .novella import Novella, PipelineError


def setup_logging():
  logging.basicConfig(level=logging.INFO)

  formatter = TerminalColorFormatter('%(message)s')
  formatter.styles.add_style('path', 'yellow')
  formatter.install()

  # lib2to3, which is used by docspec_python, logs these to the root logger on INFO, which is annoying.
  logging.root.filters.append(SimpleFilter('root', not_contains='Generating grammar tables from'))


def main():
  setup_logging()

  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('-b', '--build-directory', type=Path)
  parser.add_argument('-h', '--help', action='store_true')
  args, unknown_args = parser.parse_known_args()

  novella = Novella(Path.cwd(), args.build_directory)
  context = novella.execute_file()

  if args.help:
    novella.update_argument_parser(parser)
    parser.print_help()
    return

  try:
    novella.run_build(context, unknown_args)
  except PipelineError as exc:
    print()
    print(
      f'Uncaught exception in action "{exc.action_name}" defined at {exc.callsite.filename}:{exc.callsite.lineno}',
      file=sys.stderr,
    )
    cause = exc.__cause__
    import traceback
    traceback.print_exception(type(cause), cause, cause.__traceback__)
    sys.exit(1)


if __name__ == '__main__':
  main()
