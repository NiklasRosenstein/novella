
import logging
from re import L
import sys
import tempfile
import typing as t
from pathlib import Path

import click
import databind.json
import yaml

from . import __version__
from .context import Context
from .pipeline import Pipeline

logger = logging.getLogger(__name__)
T_Callable = t.TypeVar('T_Callable', bound=t.Callable)


_click_arguments = [
  click.option("-c", "--config", default="novella.yml", help="The Novella pipeline configuration file."),
  click.option("-h", "--help", is_flag=True),
]


def _click_apply(args: list[t.Callable]) -> t.Callable[[T_Callable], T_Callable]:
  def _decorator(f: T_Callable) -> T_Callable:
    for arg in args:
      f = arg(f)
    return f
  return _decorator


def novella_pipeline_runner(pipeline: Pipeline, config: str, **kwargs) -> None:
  for action in pipeline.actions:
    action.check_args(kwargs)
  with tempfile.TemporaryDirectory(prefix='novella-') as temp_dir:
    logger.info('Create temporary build directory %s', temp_dir)
    context = Context(Path(config).resolve().parent, Path(temp_dir), pipeline, kwargs)
    for action in pipeline.actions:
      action.execute(context)


@click.command("novella", add_help_option=False, context_settings={'ignore_unknown_options': True})
@_click_apply(_click_arguments)
@click.argument("remainder", nargs=-1)
@click.pass_context
def main(ctx: click.Context, config: str, help: bool, remainder) -> None:
  """ Execute a Novella pipeline. """

  logging.basicConfig(level=logging.INFO, format='%(message)s')
  novella_yml = Path(config)
  if not novella_yml.is_file():
    if help:
      print(ctx.get_help())
      return
    else:
      click.echo(f'File "{config}" does not exist.', err=True)
      sys.exit(1)

  try:
    pipeline = databind.json.load(yaml.safe_load(novella_yml.read_text()), Pipeline)
  except:
    if not help:
      raise

  args = _click_arguments[:]
  for action in pipeline.actions:
    action.extend_click_arguments(args)

  runner = _click_apply(args)(click.command("novella")(lambda **kw: novella_pipeline_runner(pipeline, **kw)))
  runner.help = main.help
  if help:
    print(runner.get_help(ctx))
    return

  runner()


if __name__ == '__main__':
  main()
