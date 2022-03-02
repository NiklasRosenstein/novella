
from __future__ import annotations

import argparse
import logging
import sys
import typing as t
from pathlib import Path

from nr.util.logging.filters.simple_filter import SimpleFilter
from nr.util.logging.formatters.terminal_colors import TerminalColorFormatter

from novella import __version__
from novella.action import Action
from novella.novella import Novella, PipelineError
from novella.build import NovellaBuilder

if t.TYPE_CHECKING:
  from nr.util.digraph import DiGraph


logger = logging.getLogger(__name__)


class CustomBuilder(NovellaBuilder):

  intercept_action: str | None = None

  def notify(self, action: Action, event: str, commit: t.Callable[[], t.Any] | None = None) -> None:
    if self.intercept_action is not None:
      logger.info('+ Event <fg=magenta>%s :: %s</fg>', action.name, event)
      if self.intercept_action == action.name and event == 'before_execute':
        print('Intercepted', action, event, '; press enter to continue')
        if commit:
          commit()
        input()
    return super().notify(action, event, commit)


def setup_logging() -> None:
  logging.basicConfig(level=logging.INFO)

  formatter = TerminalColorFormatter('%(message)s')
  assert formatter.styles
  formatter.styles.add_style('path', 'yellow')
  formatter.install()

  # lib2to3, which is used by docspec_python, logs these to the root logger on INFO, which is annoying.
  logging.root.filters.append(SimpleFilter('root', not_contains='Generating grammar tables from'))


def print_dotviz(graph: DiGraph[str, t.Any, t.Any]) -> None:
  print('digraph G {')
  for node in graph.nodes:
    print(f'  "{node}"')
  for edge in graph.edges:
    print(f'  "{edge[0]}" -> "{edge[1]}"')
  print('}')


def main() -> None:
  setup_logging()

  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument(
    '--version',
    action='version',
    version=__version__,
  )
  parser.add_argument(
    '-h', '--help',
    action='store_true',
    help='Show this help output.',
  )
  parser.add_argument(
    '-c', '--config-file',
    type=Path,
    default=Novella.BUILD_FILE,
    help='The configuration file to load. (default: %(default)s)',
    metavar='PATH',
  )
  parser.add_argument(
    '-b', '--build-directory',
    type=Path,
    help='The build directory. If not specified, a temporary directory will be created.',
    metavar='PATH',
  )
  parser.add_argument(
    '-r', '--use-reloader',
    action='store_true',
    help='Enable reloading, which will re-execute the pipeline if a watched file changes.',
  )
  parser.add_argument(
    '--dot',
    action='store_true',
    help='Produce a DotViz representation of the build graph.',
  )
  parser.add_argument(
    '--intercept',
    help='The name of an action to intercept and pause the execution, waiting for user input to continue. Useful '
      'for debugging intermediate steps of the build process. Currently, the action name must be matched exactly and '
      'actions can only be intercepted before they are run. If this option is provided, all possible intercept '
      'points are logged to the console.',
    metavar='ACTION',
  )
  args, unknown_args = parser.parse_known_args()

  novella = Novella(Path.cwd())

  exception: Exception | None = None
  try:
    context = novella.execute_file(Path(args.config_file) if args.config_file else None)
  except FileNotFoundError as exc:
    context = None
    exception = exc

  if args.help:
    if context:
      context.update_argument_parser(parser)
    parser.print_help()
    return

  if exception:
    raise exception

  assert context
  context.graph.build_edges()

  if args.dot:
    print_dotviz(context.graph._digraph)
    return

  builder = CustomBuilder(
    context=context,
    build_directory=Path(args.build_directory) if args.build_directory else None,
    enable_reloading=args.use_reloader,
  )
  builder.intercept_action = args.intercept

  with builder:
    context.configure(builder, unknown_args)

    try:
      builder.build()
    except PipelineError as exc:
      logger.error(
        f'<fg=red>Uncaught exception in action "{exc.action_name}" defined at '
        f'{exc.callsite.filename}:{exc.callsite.lineno}</fg>',
        exc_info=exc.__cause__,
      )
      sys.exit(1)


if __name__ == '__main__':
  main()
