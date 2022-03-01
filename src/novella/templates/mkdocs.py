
from __future__ import annotations

import dataclasses
import logging
import os
import re
import textwrap
import typing as t

from nr.util.singleton import NotSet

from novella.action import Action
from novella.build import BuildContext
from novella.markdown.flavor import MkDocsFlavor
from novella.novella import NovellaContext
from novella.template import Template
from novella.repository import detect_repository

if t.TYPE_CHECKING:
  from novella.action import CopyFilesAction, RunAction
  from novella.markdown.tags.anchor import AnchorTagProcessor
  from novella.markdown.preprocessor import MarkdownPreprocessorAction

logger = logging.getLogger(__name__)


class MkdocsTemplate(Template):
  """ A template to bootstrap an MkDocs build using Novella. It will set up actions to copy files from the
  #content_directory and the `mkdocs.yml` config relative to the Novella configuration file (if the
  configuration file exists).

  This template registers the following options:

      --serve         Use mkdocs serve
      --site-dir, -d  Build directory for MkDocs (defaults to "_site")

  This template produces the following actions:

  1. `copy-files` &ndash; A #CopyFilesAction that copies the #content_directory and the `mkdocs.yml` (if it exists)
     to the build directory.
  2. `mkdocs-update-config` &ndash; A #MkdocsApplyDefaultAction to create or update the MkDocs configuraton file.
  3. `preprocess-markdown` &ndash; An instance of the #MarkdownPreprocessorAction.
  4. `mkdocs-run` &ndash; A #RunAction that invokes MkDocs.

  If the `--serve` option is provided, the template enables file watching for everything copied by the
  `copy-files` action and marks the `mkdocs-run` as reload-capable, allowing for a seemless live editing experience
  while using Novella as a preprocessor.

  Example:

  ```py
  template "mkdocs"

  action "mkdocs-update-config" {
    site_name = "My documentation"
  }

  action "preprocess-markdown" {
    use "pydoc"
  }
  ```
  """

  #: The directory that contains the MkDocs context. Defaults to `content/`.
  content_directory: str = 'content/'

  # Template

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site-dir", "d", description='Build directory for MkDocs (defaults to "_site")', default="_site")

    def configure_copy_files(copy_files: CopyFilesAction) -> None:
      copy_files.paths = [ self.content_directory ]
      if (context.project_directory / 'mkdocs.yml').exists():
        copy_files.paths.append('mkdocs.yml')
    context.do('copy-files', configure_copy_files, name='copy-files')

    def configure_update_config(update_config: MkdocsUpdateConfigAction) -> None:
      update_config.content_directory = self.content_directory
    context.do('mkdocs-update-config', configure_update_config, name='mkdocs-update-config')

    def configure_preprocess_markdown(preprocessor: MarkdownPreprocessorAction) -> None:
      preprocessor.path = self.content_directory
      def configure_anchor(anchor: AnchorTagProcessor) -> None:
        anchor.flavor = MkDocsFlavor()
      preprocessor.preprocessor('anchor', configure_anchor)
    context.do('preprocess-markdown', configure_preprocess_markdown, name='preprocess-markdown')

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        run.supports_reloading = True
        run.args += [ "serve" ]
      else:
        run.args += [ "build", "-d", context.project_directory / str(context.options["site-dir"]) ]
    context.do('run', configure_run, name='mkdocs-run')


class MkdocsUpdateConfigAction(Action):
  """ An action to update the MkDocs configuration file, or create one if the user did not provide it.

  The following configuration serves as the default configuration if the user did not provide an MkDocs
  configuration of their own. If a configuration file is already present, it will be updated such that top-level
  keys that don't exist in the provided configuration are set to the one present in the default below.

  To disable this behaviour, set #apply_defaults to `False`.

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
  """

  _DEFAULT_CONFIG: str = textwrap.dedent(re.search(r'```(.*?)```', __doc__, re.S).group(1))  # type: ignore

  #: Whether to apply the template to the MkDocs configuration (shown above).
  apply_defaults: bool = True

  #: The MkDocs `site_name` to inject. Will override an existing site name if not present in the MkDocs configuration.
  site_name: str | None = None

  #: Whether to autodetect the Git repository URL and inject it into the MkDocs configuration. Enabled by
  #: default. If the repository URL is already configured, it will do nothing.
  autodetect_repo_url: bool = True

  #: The content directory that contains the MkDocs source files. This is used only to construct the edit URI if
  #: #autodetect_repo_url is enabled. This passed through by the #MkdocsTemplate automatically.
  content_directory: str

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
    template "mkdocs"

    action "mkdocs-update-config" {
      site_name = "My documentation"
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

    if self.apply_defaults:
      default_config = yaml.safe_load(self._DEFAULT_CONFIG)
      for key in default_config:
        if key not in mkdocs_config:
          mkdocs_config[key] = default_config[key]

    if self.site_name:
      mkdocs_config['site_name'] = self.site_name

    if self.autodetect_repo_url:
      repo_info = detect_repository(self.context.project_directory)
      if 'repo_url' not in mkdocs_config and repo_info:
          mkdocs_config['repo_url'] = repo_info.url
          logger.info('Detected Git repository URL: <fg=cyan>%s</fg>', repo_info.url)
      else:
        logger.warning('Could not detect Git repository URL')
      if 'edit_uri' not in mkdocs_config and repo_info:
        content_dir = (self.context.project_directory / self.content_directory)
        edit_uri = f'blob/{repo_info.branch}/' + str(content_dir.relative_to(repo_info.root))
        mkdocs_config['edit_uri'] = edit_uri
        logger.info('Detected edit URI: <fg=cyan>%s</fg>', edit_uri)

    for mutator in self._updaters:
      mutator(mkdocs_config)

    if original_config != mkdocs_config:
      logger.info('%s <fg=yellow>%s</fg>', 'Updating' if mkdocs_yml.exists() else 'Generating new', mkdocs_yml)
      mkdocs_yml.write_text(yaml.dump(mkdocs_config))
