
from __future__ import annotations

import dataclasses
import logging
import os
import re
import textwrap
import typing as t

from nr.util.singleton import NotSet

from markdown.extensions.toc import slugify
from novella.action import Action
from novella.build import BuildContext
from novella.novella import NovellaContext
from novella.template import Template
from novella.tags.anchor import AnchorAndLinkRenderer
from novella.repository import detect_repository

if t.TYPE_CHECKING:
  from nr.util.functional import Supplier
  from novella.action import CopyFilesAction, RunAction
  from novella.markdown.preprocessor import MarkdownPreprocessorAction
  from novella.tags.anchor import Anchor, AnchorTagProcessor, Link

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MkdocsMkdocsAnchorAndLinkRenderer(AnchorAndLinkRenderer):

  #: The content directory, specified as a supplier because it should always reference the content directory
  #: that is configured in the #MkdocsTemplate settings.
  content_directory: Supplier[str]

  #: Whether links should be rendered relatively to other pages. Disabled by default.
  relative_links: bool = False

  #: If #relative_links is disabled, this is prepended to generated absolute link URLs. If your site is
  #: not hosted at the root of your web server, you may need to set this value. The string should end in
  #: a slash.
  path_prefix: str = ''

  def _get_anchor_html_id(self, anchor: Anchor) -> str:
    if anchor.header_text:
      return slugify(anchor.header_text.lower(), '-')
    return anchor.id

  def _get_absolute_href(self, link: Link) -> str:
    assert link.target
    path = link.target.file
    if path.name == 'index.md':
      path = path.parent
    else:
      path = path.with_suffix('')
    url_path = str(path.relative_to(self.content_directory())).replace(os.sep, '/')
    if url_path == os.curdir:
      url_path = ''
    return f'/{self.path_prefix}{url_path}#{self._get_anchor_html_id(link.target)}'

  def _get_relative_href(self, link: Link) -> str:
    assert link.target
    # TODO (@NiklasRosenstein): Sanitize how we find the correct relative HREF to other pages.
    target = os.path.relpath(link.target.file.with_suffix(''), link.file.parent).replace(os.sep, '/')
    if target == 'index':
      target = '..'
    elif target.startswith('../') and target.endswith('/index'):
      target = target.removesuffix('/index') + '/..'
    target = target.removesuffix('/index')
    return target + '#' + self._get_anchor_html_id(link.target)

  def render_anchor(self, anchor: Anchor) -> str | None:
    if not anchor.header_text:
      return f'<a id="{anchor.id}"></a>'
    return ''

  def render_link(self, link: Link) -> str:
    if not link.target:
      return f'{{@link {link.anchor_id}}}'
    if link.target.file == link.file:
      href = '#' + self._get_anchor_html_id(link.target)
    else:
      href = self._get_relative_href(link) if self.relative_links else self._get_absolute_href(link)
    return f'<a href="{href}">{link.text or link.target.text or link.target.header_text}</a>'


class MkdocsTemplate(Template):
  """ A template to bootstrap an MkDocs build using Novella. It will set up actions to copy files from the
  {@attr content_directory} and the `mkdocs.yml` config relative to the Novella configuration file (if the
  configuration file exists). Then, unless {@attr apply_default_config} is disabled, it will apply a default
  configuration that is delivered alongside the template (using the MkDocs-material theme and enabling a
  bunch of Markdown extensions), and then run MkDocs to either serve or build the documentation.

  The template registers the following options:

      --serve         Use mkdocs serve
      --site-dir, -d  Build directory for MkDocs (defaults to "_site")

  The template produces the following actions:

  1. `mkdocs-copy-files` &ndash; a `copy-files` action to copy the #content_directory and the `mkdocs.yml` (if it
     exists) to the build directory.
  2. `mkdocs-update-config` &ndash; An internal action provided by the MkDocs template to either create an `mkdocs.yml`
     or apply defaults from the template delivered with Novella. Check out the #MkdocsApplyDefaultAction for more
     details.
  3. `mkdocs-preprocess-markdown` &ndash; An instance of the `preprocess-markdown` action, setup with builtin
     preprocessors such as `cat` and `anchor`. The anchor plugin is preconfigured with a
     #MkdocsMkdocsAnchorAndLinkRenderer instance which renders the correct links for MkDocs compatible markdown files.
  4. `mkdocs-run` &ndash; A `run` action that invokes `mkdocs build`, or `mkdocs serve` if the `--serve` option is
     provided.

  If the `--serve` option is provided, the template enables file watching for everything copied by the
  `mkdocs-copy-files` action and marks the `mkdocs-run` as reload-capable, allowing for a seemless live
  editing experience while using Novella as a preprocessor.

  __Example__

  ```py
  template "mkdocs" {
    site_name = "Novella"
  }

  action "mkdocs-preprocess-markdown" {
    preprocessor "anchor" {
      renderer.relative_links = True
    }
  }
  ```
  """

  #: The directory that contains the MkDocs context.
  content_directory: str = 'content'

  #: Apply the default MkDocs configuration provided by this template. This action is performed by the
  #: #MkdocsUpdateConfigAction. Enabled by default.
  apply_default: bool = True

  #: The site name to put into the `mkdocs.yml`. Overrides the site name if it is configured in your MkDocs
  #: configuration file. This action is performed by the #MkdocsUpdateConfigAction.
  site_name: str | None = None

  #: Whether the Git repository URL should be automatically detected in #MkdocsUpdateConfigAction. Only if
  #: the `repo_url` setting in the MkDocs config is not already set, and if #repository is not set.
  autodetect_repo_url: bool = True

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site-dir", "d", description='Build directory for MkDocs (defaults to "_site")', default="_site")

    def configure_copy_files(copy_files: CopyFilesAction) -> None:
      copy_files.paths = [ self.content_directory ]
      if (context.project_directory / 'mkdocs.yml').exists():
        copy_files.paths.append('mkdocs.yml')
    context.do('copy-files', configure_copy_files, name='mkdocs-copy-files')

    def configure_update_config(update_config: MkdocsUpdateConfigAction) -> None:
      update_config.template = self
    context.do('mkdocs-update-config', configure_update_config, name='mkdocs-update-config')

    def configure_preprocess_markdown(preprocessor: MarkdownPreprocessorAction) -> None:
      preprocessor.use('shell')
      preprocessor.use('cat')
      def configure_anchor(anchor: AnchorTagProcessor) -> None:
        anchor.renderer = MkdocsMkdocsAnchorAndLinkRenderer(lambda: self.content_directory)
      preprocessor.use('anchor', configure_anchor)
    context.do('preprocess-markdown', configure_preprocess_markdown, name='mkdocs-preprocess-markdown')

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        run.supports_reloading = True
        run.args += [ "serve" ]
      else:
        run.args += [ "build", "-d", context.project_directory / str(context.options["site-dir"]) ]
    context.do('run', configure_run, name='mkdocs-run')


class MkdocsUpdateConfigAction(Action):
  r""" An action to update the MkDocs configuration file, or create one if the user did not provide it.

  __Configuration defaults__

  The following configuration serves as the default configuration if the user did not provide an MkDocs
  configuration of their own. If a configuration file is already present, it will be updated such that top-level
  keys that don't exist in the provided configuration are set to the one present in the default below.

  To disable this behaviour, set #MkdocsTemplate.apply_default to `False`.

  ```
  docs_dir: content
  site_name: My documentation
  theme:
    name: material
    features:
    - navigation.indexes
    - navigation.instant
    - navigation.tracking
    - navigation.top
    - toc.follow
  markdown_extensions:
  - admonition
  - markdown.extensions.extra
  - meta
  - pymdownx.betterem
  - pymdownx.caret
  - pymdownx.details
  - pymdownx.highlight
  - pymdownx.inlinehilite
  - pymdownx.keys
  - pymdownx.mark
  - pymdownx.smartsymbols
  - pymdownx.superfences
  - pymdownx.tabbed: { alternate_style: true }
  - pymdownx.tasklist: { custom_checkbox: true }
  - pymdownx.tilde
  ```

  Check out the the [Material for MkDocs // Setup](https://squidfunk.github.io/mkdocs-material/setup/changing-the-colors/)
  documentation for more information. Other common theme features to enable are `toc.integrate` and `navigation.tabs`.

  __Site name__

  The site name can be updated from the Novella configuration, usually through #MkdocsTemplate.site_name.

  __Autodetect Git repository__

  Automatically detect the Git repository URL and inject it into the MkDocs `repo_url` and `edit_url`
  options unless already configure and only if the #MkdocsTemplate.autodetect_repo_url is enabled. This is enabled
  by default.

  __Update instructions__

  Using the #update() method, a string similar to JSONpath and an operation can be provided that will be applied to
  the MkDocs configuration. A function to update the MkDocs configuration can be specified with the #update_func()
  method.
  """

  _DEFAULT_CONFIG: str = textwrap.dedent(re.search(r'```(.*?)```', __doc__, re.S).group(1))  # type: ignore

  template: MkdocsTemplate

  def update(self, json_path: str, *, add: t.Any = NotSet.Value, set: t.Any = NotSet.Value, do: t.Callable[[t.Any], t.Any] | None = None) -> None:
    """ A helper function to update a value in the MkDocs configuration by either setting it to the
    value specified to the *set* argument or by adding to it (e.g. updating it if it is a dictionary
    or summing them in case of other values like strings or lists) the value of *add*. The *do* operation
    can also be used to perform an action on the existing value at *json_path*, but the value must be
    directly mutated and already exist in the configuration.

    Note that the *json_path* argument is treated very simplisticly and does not support wildcards or
    indexing. The string must begin with `$`. Quotes in keys are not supported either.

    __Example__


    ```py
    action "mkdocs-update-config" {
      update '$.theme.features' add: ['toc.integrate', 'navigation.tabs']
      update '$.theme.palette' set: {'primary': 'black', 'accent': 'amber'}
    }
    ```
    """

    arg_count = sum([add is not NotSet.Value, set is not NotSet.Value, do is not None])
    if arg_count == 0:
      raise ValueError('missing "add", "set" or "do" argument')
    elif arg_count > 1:
      raise ValueError('incompatible arguments')

    parts = json_path.split('.')
    if parts[0] != '$':
      raise ValueError(f'invalid json_path, must begin with `$.`: {json_path!r}')

    def _mutator(config: dict[str, t.Any]) -> None:
      for part in parts[1:-1]:
        if part not in config:
          config[part] = {}
        config = config[part]
      part = parts[-1]
      if do is not None:
        do(config[part])
      elif part not in config or set is not NotSet.Value:
        config[part] = add if set is NotSet.Value else set
      else:
        if isinstance(config[part], dict):
          config[part] = {**config[part], **add}
        else:
          config[part] = config[part] + add

    self._updaters.append(_mutator)

  def update_with(self, func: t.Callable[[dict[str, t.Any]], t.Any]) -> None:
    """ Adds a callback that can modify the MkDocs config before it is updated. """

    self._updaters.append(func)

  # Action

  def __post_init__(self) -> None:
    self._updaters: list[t.Callable] = []

  def execute(self, build: BuildContext) -> None:
    import copy
    import yaml

    mkdocs_yml = build.directory / 'mkdocs.yml'

    if mkdocs_yml.exists():
      mkdocs_config = yaml.safe_load(mkdocs_yml.read_text())
    else:
      mkdocs_config = {}
    original_config = copy.deepcopy(mkdocs_config)

    if self.template.apply_default:
      default_config = yaml.safe_load(self._DEFAULT_CONFIG)
      for key in default_config:
        if key not in mkdocs_config:
          mkdocs_config[key] = default_config[key]

    if self.template.site_name:
      mkdocs_config['site_name'] = self.template.site_name

    if self.template.autodetect_repo_url:
      repo_info = detect_repository(self.context.project_directory)
      if 'repo_url' not in mkdocs_config and repo_info:
          mkdocs_config['repo_url'] = repo_info.url
          logger.info('Detected Git repository URL: <fg=cyan>%s</fg>', repo_info.url)
      else:
        logger.warning('Could not detect Git repository URL')
      if 'edit_uri' not in mkdocs_config and repo_info:
        content_dir = (self.context.project_directory / self.template.content_directory)
        edit_uri = f'blob/{repo_info.branch}/' + str(content_dir.relative_to(repo_info.root))
        mkdocs_config['edit_uri'] = edit_uri
        logger.info('Detected edit URI: <fg=cyan>%s</fg>', edit_uri)

    for mutator in self._updaters:
      mutator(mkdocs_config)

    if original_config != mkdocs_config:
      logger.info('%s <fg=yellow>%s</fg>', 'Updating' if mkdocs_yml.exists() else 'Generating new', mkdocs_yml)
      mkdocs_yml.write_text(yaml.dump(mkdocs_config))
