
from __future__ import annotations

import enum
import typing as t
from pathlib import Path

from novella.compat import removesuffix


class RepositoryType(enum.Enum):
  GIT = enum.auto()


class RepositoryDetails(t.NamedTuple):
  type: RepositoryType
  root: Path
  url: str
  branch: str | None


def detect_repository(path: Path) -> RepositoryDetails | None:
  """ Detects the repository details from the given path.

  Currently supports only Git repositories. Does a simplistic attempt to convert SSH URLs to HTTPS.
  """

  from nr.util.git import Git, NoCurrentBranchError

  git = Git(path)
  if not (toplevel := git.get_toplevel()):
    return None

  remote = next(iter(git.remotes()), None)
  if not remote:
    return None

  url = remote.fetch
  if url.startswith('git@'):
    url = 'https://' + url[4:].replace(':', '/')
  url = removesuffix(url, '.git')

  try:
    branch = git.get_current_branch_name()
  except NoCurrentBranchError:
    branch = None

  return RepositoryDetails(RepositoryType.GIT, Path(toplevel), url, branch)
