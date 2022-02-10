
import argparse
from pathlib import Path

from .novella import Novella


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('-b', '--build-directory', type=Path)
  args = parser.parse_args()

  novella = Novella(Path.cwd(), args.build_directory)
  novella.execute_file()
  novella.build()


if __name__ == '__main__':
  main()
