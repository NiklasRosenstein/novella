
import argparse
import logging
import tempfile
from pathlib import Path

import yaml
import databind.json

from . import Context, Pipeline

logger = logging.getLogger(__name__)


def get_argument_parser():
  parser = argparse.ArgumentParser()
  parser.add_argument('-c', '--config', default='novella.yml')
  return parser


def main():
  parser = get_argument_parser()
  args = parser.parse_args()
  logging.basicConfig(level=logging.INFO, format='%(message)s')
  pipeline = databind.json.load(yaml.safe_load(Path(args.config).read_text()), Pipeline)

  with tempfile.TemporaryDirectory(prefix='novella-') as temp_dir:
    logger.info('Create temporary build directory %s', temp_dir)
    context = Context(Path('.'), Path(temp_dir), pipeline)
    for action in pipeline.actions:
      action.execute(context)


if __name__ == '__main__':
  main()
