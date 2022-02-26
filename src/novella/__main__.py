
import argparse
from fnmatch import fnmatch
import logging
import sys
import typing as t
from pathlib import Path

from nr.util.logging.filters.simple_filter import SimpleFilter
from nr.util.logging.formatters.terminal_colors import TerminalColorFormatter

from novella.action import Action
from novella.novella import Novella, PipelineError
from novella.build import NovellaBuilder

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


def main() -> None:
  setup_logging()

  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('-b', '--build-directory', type=Path)
  parser.add_argument('-h', '--help', action='store_true')
  parser.add_argument('-r', '--use-reloader', action='store_true')
  parser.add_argument('--intercept')
  args, unknown_args = parser.parse_known_args()

  novella = Novella(Path.cwd())
  context = novella.execute_file()

  if args.help:
    context.update_argument_parser(parser)
    parser.print_help()
    return

  context.configure(unknown_args)
  builder = CustomBuilder(
    context=context,
    build_directory=Path(args.build_directory) if args.build_directory else None,
    enable_reloading=args.use_reloader,
  )
  builder.intercept_action = args.intercept

  try:
    builder.build()
  except PipelineError as exc:
    logger.error(
      f'<fg=red>Uncaught exception in action "{exc.action_name}" defined at '
      f'{exc.callsite.filename}:{exc.callsite.lineno}</fg>',
      exc_info=exc.__cause__
    )
    sys.exit(1)


if __name__ == '__main__':
  main()
