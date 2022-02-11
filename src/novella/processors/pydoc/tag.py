
import logging
import typing as t
from collections import ChainMap
from pathlib import Path

import mako.lookup, mako.runtime, mako.template
from docspec import ApiObject, Module, visit

from novella.processor import NovellaTagProcessor
from .loader import PythonLoader

logger = logging.getLogger(__name__)


class PydocTagProcessor(NovellaTagProcessor):
  """ Processor for the `@pydoc` tag that replaces references with Markdown content that was rendered through Mako
  templates. The output can be customized by modifying the options understood by the default template, or by providing
  custom templates.

  __Example__

      @pydoc :set header_level = 3
      @pydoc novella.novella.Novella :with { classdef_code = false }

  The Pydoc processor comes with a set of default templates:

    * `/base/entrypoint.mako` &ndash; The main template to which the {@class docspec.ApiObject} is passed, optionally
      togther with the options and a `parent` reference to identify if the template is rendered as a child from an
      API object's members. The template dispatches to one of the other templates below and implements any kinds of
      filters.
    * `/base/helpers.mako` &ndash; A template that contains some helper functions that can be included using the
      Mako `<%namespace/>` tag into another template.
    * `/base/class.mako`
    * `/base/data.mako`
    * `/base/functions.mako`

  The `base` templates support the following options to modify the templates that are used to render.

  * `templates.entrypoint`: Defaults to `/base/entrypoint.mako`
  * `templates.class`: Defaults to `/base/class.mako`
  * `templates.function`: Defaults to `/base/function.mako`
  * `templates.data`: Defaults to `/base/data.mako`
  * `templates.helpers`: Defaults to `/base/helpers.mako`

  Furthermore, the default templates support these options:

  * `absolute_fqn` (`bool`) &ndash; Whether to render the absolute FQN. Defaults to `True`
  * `exclude_undocumented` (`bool`) &ndash; Whether to exclude undocumented API objects unless they are explicitly
    required by a `@pydoc` tag.
  * `header_level` (`int`) &ndash; The initial Markdown header level. Defaults to `2`.
  * `render_module_name_after_title' (`bool`) &ndash; Place the module name after the header. Defaults to `False`.
  * `render_class_def` (`bool`) &ndash; Whether a code block with a classes' definition should be rendered. Defaults to `True`
  * `render_class_attrs` (`bool`) &ndash; True
  * `render_class_methods` (`bool`) &ndash; True
  * `render_class_hr` (`bool`) &ndash; True
  * `render_data_def` (`bool`) &ndash; True
  * `render_func_def` (`bool`) &ndash; Whether a code block with a functions' definition should be rendered. Defaults to `True`
  * `render_module_name_after_title` (`bool)` &ndash; False
  * `render_title` (`bool`) &ndash; True
  """

  tag_name = 'pydoc'

  def __init__(self) -> None:
    super().__init__()
    self.loader = PythonLoader()
    self.template_directories: list[str] = []
    self._modules: list[Module] | None = None
    self.options = {
      'templates': {
        'entrypoint': '/base/entrypoint.mako',
        'class': '/base/class.mako',
        'function': '/base/function.mako',
        'data': '/base/data.mako',
        'helpers': '/base/helpers.mako',
      },
      'absolute_fqn': True,
      'exclude_undocumented': True,
      'header_level': 2,
      'render_class_def': True,
      'render_class_attrs': True,
      'render_class_methods': True,
      'render_class_hr': True,
      'render_data_def': True,
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

    def _render(template_name: str, obj: ApiObject, parent: ApiObject | None = None, **override_options):
      template = lookup.get_template(template_name)
      return template.render(
        novella=self.current.novella,
        render=_render,
        lookup=lookup,
        obj=obj,
        parent=parent,
        options=_MakoContext(ChainMap(override_options, options), 'options.'),
      )

    return _render(options['templates']['entrypoint'], obj)


class _MakoContext:

  def __init__(self, mapping: t.Mapping[str, t.Any], prefix: str = '') -> None:
    self._mapping = mapping
    self._prefix = prefix

  def __getitem__(self, name: str) -> t.Any:
    return self.__getattr__(name)

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
