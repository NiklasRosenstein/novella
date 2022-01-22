
import argparse
import logging
import tempfile
from pathlib import Path

import yaml
import databind.json

from . import Context, Pipeline

logger = logging.getLogger(__name__)


def get_argument_parser():
  parser = argparse.ArgumentParser(add_help=False, prog='novella')
  parser.add_argument('-h', '--help', action='store_true')
  parser.add_argument('-c', '--config', default='novella.yml')
  return parser


def main():
  parser = get_argument_parser()
  args = parser.parse_known_args()[0]

  logging.basicConfig(level=logging.INFO, format='%(message)s')
  pipeline = databind.json.load(yaml.safe_load(Path(args.config).read_text()), Pipeline)

  for action in pipeline.actions:
    action.extend_cli_parser(parser)
  args = parser.parse_args()

  if args.help:
    parser.print_help()
    return

  for action in pipeline.actions:
    action.check_args(parser, args)

  with tempfile.TemporaryDirectory(prefix='novella-') as temp_dir:
    logger.info('Create temporary build directory %s', temp_dir)
    context = Context(Path('.').resolve(), Path(temp_dir), pipeline, args)
    for action in pipeline.actions:
      action.execute(context)


if __name__ == '__main__':
  main()
