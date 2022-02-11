
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
  * `templates.class_attrs_table`: Defaults to `/base/data_table.mako`
  * `templates.class_method_table`: Defaults to `/base/function_table.mako`
  * `templates.function`: Defaults to `/base/function.mako`
  * `templates.data`: Defaults to `/base/data.mako`
  * `templates.helpers`: Defaults to `/base/helpers.mako`
  """

  tag_name = 'pydoc'

  #: The loader for Python API documentation.
  loader: PythonLoader

  #: A list of paths relative to the project directory to load templates from in addition to the builtin templates.
  #: This must be set if you want to use custom Markdown templates to generate Python API documentation.
  template_directories: list[str]

  #: A dictionary of options to pass into the "options" object in the Mako templates. By default, it contains
  #: default values for the all the options understood by the builtin base templates.
  options: dict[str, t.Any]

  def __init__(self) -> None:
    super().__init__()
    self.loader = PythonLoader()
    self.template_directories = []
    self._modules: list[Module] | None = None
    self.options = {
      'templates': {
        'entrypoint': '/base/entrypoint.mako',
        'class': '/base/class.mako',
        'class_attrs_table': '/base/data_table.mako',
        'class_method_table': '/base/function_table.mako',
        'function': '/base/function.mako',
        'data': '/base/data.mako',
        'helpers': '/base/helpers.mako',
      },
      'header_level': {
        'module': 2,
        'module_member': 3,
        'class': 2,
        'class_member': 3,
        'function': 2,
      },
      'absolute_fqn': False,
      'exclude_undocumented': True,
      'render_class_def': True,
      'render_class_attrs': False,
      'render_class_attrs_summary': True,
      'render_class_method_table': True,
      'render_class_methods': True,
      'render_class_hr': True,
      'render_data_def': True,
      'render_func_def': True,
      'render_func_typehints': True,
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

    def _render(
      template_name: str,
      obj: ApiObject,
      parent: ApiObject | None = None,
      override_options: t.Mapping[str, t.Any] | None = None,
      **context
    ) -> str:
      template = lookup.get_template(template_name)
      return template.render(
        novella=self.current.novella,
        render=_render,
        lookup=lookup,
        obj=obj,
        parent=parent,
        #register_header=self._register_header,
        options=_MakoContext(ChainMap(override_options or {}, options), 'options.'),
        **context,
      )

    return _render(options['templates']['entrypoint'], obj)

  def _register_header(self, markdown_header: str, obj: ApiObject, id: str | None = None) -> None:
    """ This method is exposed as `register_markdown` to Mako templates and should be called when the documentation
    for *obj* is rendered into the current page to record what page and HTML element to link to for the object. """


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
      logger.warning('    warning: Access to non-existent key <error>%r</error> from <path>%r</path>', self._prefix + name, filename)
      return mako.runtime.Undefined()
    if isinstance(result, t.Mapping):
      result = _MakoContext(result, self._prefix + name + '.')
    return result
