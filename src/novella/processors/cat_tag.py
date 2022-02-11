
import typing as t
from pathlib import Path

from novella.novella import Novella
from novella.processor import NovellaTagProcessor


class CatTagProcessor(NovellaTagProcessor):
  """ Replaces `@cat <filename>` tags with the contents of the referenced filename. The string `$project` may be
  used in the filename argument to reference the project directory; otherwise the path will be considered relative
  to the current file in the project directory (not the temporary build directory). """

  tag_name = 'cat'

  def replace_tag(self, args: str, options: dict[str, t.Any]) -> str | None:
    novella = self.current.novella
    if '$project' in args:
      path = Path(args.replace('$project', str(novella.project_directory)).strip())
    else:
      path = (novella.project_directory / path.parent.relative_to(novella.build_directory) / args.strip()).resolve()
    return path.resolve().read_text()
