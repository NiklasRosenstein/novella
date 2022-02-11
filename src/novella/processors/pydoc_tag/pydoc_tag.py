
from email.errors import UndecodableBytesDefect
import logging
import typing as t
from collections import ChainMap
from pathlib import Path

import mako.lookup, mako.runtime, mako.template
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
  | `header_level` | `int` | The initial Markdown header level. Defaults to `2`. |
  | `render_module_name_after_title' | `bool` | Place the module name after the header. Defaults to `False`. |
  | `render_class_def` | `bool` | Whether a code block with a classes' definition should be rendered. Defaults to `True` |
  | `render_class_attrs` | `bool` | |
  | `render_class_methods` | `bool` | |
  | `render_class_hr` | `bool` | |
  | `render_func_def` | `bool` | Whether a code block with a functions' definition should be rendered. Defaults to `True` |
  | `render_title` | `bool` | |
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
      'render_class_def': True,
      'render_class_attrs': True,
      'render_class_methods': True,
      'render_class_hr': True,
      'render_func_def': True,
      'render_module_name_after_title': False,
      'render_title': True,
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
      results[0],
      ChainMap(options, self.file_options, self.options),
    )

  def _render_as_markdown(self, obj: ApiObject, options: t.Mapping[str, t.Any]) -> str:

    local_directory = Path(__file__).parent / 'templates'
    lookup = mako.lookup.TemplateLookup([local_directory] + self.template_directories)

    def _render(template_name: str, obj: ApiObject, **override_options):
      template = lookup.get_template(template_name)
      return template.render(
        novella=self.current.novella,
        render=_render,
        lookup=lookup,
        obj=obj,
        options=_MakoContext(ChainMap(override_options, options), 'options.'),
      )

    return _render('api_object.mako', obj)


class _MakoContext:

  def __init__(self, mapping: t.Mapping[str, t.Any], prefix: str = '') -> None:
    self._mapping = mapping
    self._prefix = prefix

  def __getattr__(self, name: str) -> t.Any:
    try:
      result = self._mapping[name]
    except KeyError:
      from nr.util.inspect import get_callsite
      filename = get_callsite().filename
      logger.warning('Access to non-existent %r from %r', self._prefix + name, filename)
      return mako.runtime.Undefined
    if isinstance(result, t.Mapping):
      result = _MakoContext(result, self._prefix + name + '.')
    return result
