

import dataclasses
import logging
import typing as t

import jinja2
from docspec import ApiObject, Function
from docspec_python import format_arglist

from novella.novella import Novella

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class JinjaPythonApiRenderer:
  """ Renderer for Python API objects using Jinja templates. Comes with a default template. """

  #: One or more directories from which to load templates. Template files in these directoties will take priority
  #: over the default templates delivered with Novella.
  directories: list[str] | None = None

  def render_as_markdown(self, novella: Novella, fqn: str, obj: ApiObject, options: list[str]) -> str:
    env = jinja2.Environment(loader=jinja2.ChoiceLoader([
      jinja2.PackageLoader(__name__),
      jinja2.FileSystemLoader(self.directories or []),
    ]))
    env.filters['arglist'] = _arglist
    env.filters['fqn'] = _fqn
    env.filters['type'] = _type
    env.globals['options'] = options
    return env.get_template('api_object.jinja').render(novella=novella, user_fqn=fqn, obj=obj)


def _arglist(obj: Function, type_hints: bool = False) -> str:
  return format_arglist(obj.args, type_hints)


def _fqn(obj: ApiObject) -> str:
  return '.'.join(x.name for x in obj.path)


def _type(obj: t.Any) -> str:
  return type(obj).__name__
