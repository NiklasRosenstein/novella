
import logging
import typing as t
from collections import ChainMap

import jinja2
from docspec import ApiObject, Function, Module, visit
from docspec_python import format_arglist

from novella.markdown.processor import NovellaTagProcessor
from novella.novella import Novella
from .loader import PythonLoader

logger = logging.getLogger(__name__)


class PydocProcessor(NovellaTagProcessor):
  """ Processor for the `@pydoc` tag that replaces references with Markdown content that was rendered through Jinja
  templates. The output can be customized by overriding the Jinja templates or using one of the available options.

  __Example__

      @pydoc :set header_level = 3
      @pydoc novella.novella.Novella :with { classdef_code = false }

  The following options are understood by the default template:

  | Option name | Type | Description |
  | ----------- | ---- | ----------- |
  | `absolute_fqn` | `bool` | Whether to render the absolute FQN. Defaults to `True` |
  | `classdef_code` | `bool` | Whether a code block with a classes' definition should be rendered. Defaults to `True` |
  | `funcdef_code` | `bool` | Whether a code block with a functions' definition should be rendered. Defaults to `True` |
  | `header_level` | `int` | The initial Markdown header level. Defaults to `2`. |
  | `module_after_header' | `bool` | Place the module name after the header. Defaults to `False`. |
  """

  tag_name = 'pydoc'

  def __init__(self) -> None:
    super().__init__()
    self.loader = PythonLoader()
    self.template_directories: list[str] = []
    self._modules: list[Module] | None = None
    self.options = {
      'absolute_fqn': True,
      'header_level': 2,
      'classdef_code': True,
      'funcdef_code': True,
      'module_after_header': False,
    }

  def replace_tag(self, args: str, options: dict[str, t.Any]) -> str | None:

    object_fqn = args.strip()

    if self._modules is None:
      self._modules = self.loader.load_all(self.current.novella.project_directory)

    if not self._modules:
      self.log('warning', 'Could not load modules')
      return None

    # TODO (@NiklasRosenstein): Add helper function to docspec to resolve by FQN (respecting imports).

    def _match(results: list[ApiObject]) -> t.Callable[[ApiObject], t.Any]:
      def matcher(obj: ApiObject) -> None:
        fqn = '.'.join(y.name for y in obj.path)
        if fqn == object_fqn:
          results.append(obj)
      return matcher

    results: list[ApiObject] = []
    visit(self._modules, _match(results))
    if not results:
      self.log('warning', 'Could not resolve %s', object_fqn)
      return None

    return self._render_as_markdown(
      object_fqn,
      results[0],
      ChainMap(options, self.file_options, self.options),
    )

  def _render_as_markdown(self, fqn: str, obj: ApiObject, options: t.Mapping[str, t.Any]) -> str:

    env = jinja2.Environment(loader=jinja2.ChoiceLoader([
      jinja2.PackageLoader(__name__),
      jinja2.FileSystemLoader(self.template_directories or []),
    ]))

    def _render(template_name: str, **override_options):
      template = env.get_template(template_name)
      return template.render(
        novella=self.current.novella,
        **ChainMap(override_options, options),
      )

    env.filters['arglist'] = _arglist
    env.filters['fqn'] = _fqn
    env.filters['type'] = _type
    env.globals['render'] = _render

    return _render('api_object.jinja', user_fqn=fqn, obj=obj)


def _arglist(obj: Function, type_hints: bool = False) -> str:
  return format_arglist(obj.args, type_hints)


def _fqn(obj: ApiObject) -> str:
  return '.'.join(x.name for x in obj.path)


def _type(obj: t.Any) -> str:
  return type(obj).__name__
