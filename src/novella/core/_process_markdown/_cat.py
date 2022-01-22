
import dataclasses
from pathlib import Path

from . import MarkdownTagProcessor
from .. import Context


@dataclasses.dataclass
class CatMarkdownProcessor(MarkdownTagProcessor):
  """ Replaces `@cat <filename>` tags with the contents of the referenced filename. The string `$project` may be
  used in the filename argument to reference the project directory; otherwise the path will be considered relative
  to the current file in the project directory (not the temporary build directory). """

  def process_tag(self, context: Context, path: Path, tag_name: str, args: str) -> str | None:
    if tag_name != 'cat':
      return

    if '$project' in args:
      path = Path(args.replace('$project', str(context.project_directory)).strip())
    else:
      path = (context.project_directory / path.parent.relative_to(context.build_directory) / args.strip()).resolve()

    return path.resolve().read_text()
