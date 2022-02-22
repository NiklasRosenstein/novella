
from __future__ import annotations

import dataclasses
import logging
import os
import re
import textwrap
import typing as t
from pathlib import Path

from nr.util.functional import Supplier

from novella.action import Action, ActionSemantics
from novella.novella import NovellaContext
from novella.template import Template
from novella.tags.anchor import AnchorAndLinkRenderer

if t.TYPE_CHECKING:
  from novella.action import RunAction
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
      # TODO (@NiklasRosenstein): Sanitize the Markdown header in the same way as MkDocs.
      return anchor.header_text.lower()
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
  #: the `repo_url` setting is not already set.
  autodetect_repo_url: bool = True

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site-dir", "d", description='Build directory for MkDocs (defaults to "_site")', default="_site")

    def configure_copy_files(copy_files):
      copy_files.paths = [ self.content_directory ]
      if (context.project_directory / 'mkdocs.yml').exists():
        copy_files.paths.append('mkdocs.yml')
    context.do('copy-files', configure_copy_files, name='mkdocs-copy-files')

    def configure_update_config(update_config: MkdocsUpdateConfigAction):
      update_config.template = self
    context.do('mkdocs-update-config', configure_update_config, name='mkdocs-update-config')

    def configure_preprocess_markdown(preprocessor: MarkdownPreprocessorAction):
      preprocessor.use('shell')
      preprocessor.use('cat')
      def configure_anchor(anchor: AnchorTagProcessor):
        anchor.renderer = MkdocsMkdocsAnchorAndLinkRenderer(lambda: self.content_directory)
      preprocessor.use('anchor', configure_anchor)
    context.do('preprocess-markdown', configure_preprocess_markdown, name='mkdocs-preprocess-markdown')

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        context.enable_file_watching()
        run.flags = ActionSemantics.HAS_INTERNAL_RELOADER
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
  theme: material
  markdown_extensions:
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

  __Site name__

  The site name can be updated from the Novella configuration, usually through #MkdocsTemplate.site_name.

  __Autodetect Git repository__

  Automatically detect the Git repository URL and inject it into the MkDocs `repo_url` and `edit_url`
  options unless already configure and only if the #MkdocsTemplate.autodetect_repo_url is enabled. This is enabled
  by default.
  """

  _DEFAULT_CONFIG: str = textwrap.dedent(re.search(r'```(.*?)```', __doc__, re.S).group(1))  # type: ignore

  template: MkdocsTemplate

  def execute(self) -> None:
    import copy
    import yaml

    mkdocs_yml = self.novella.build.directory / 'mkdocs.yml'

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
      repo_info = get_repository_details(self.novella.project_directory)
      if 'repo_url' not in mkdocs_config and repo_info:
          mkdocs_config['repo_url'] = repo_info.url
          logger.info('Detected Git repository URL: <fg=cyan>%s</fg>', repo_info.url)
      else:
        logger.warning('Could not detect Git repository URL')
      if 'edit_uri' not in mkdocs_config and repo_info:
        content_dir = (self.novella.project_directory / self.template.content_directory)
        edit_uri = f'blob/{repo_info.branch}/' + str(content_dir.relative_to(repo_info.root))
        mkdocs_config['edit_uri'] = edit_uri
        logger.info('Detected edit URI: <fg=cyan>%s</fg>', edit_uri)

    if original_config != mkdocs_config:
      logger.info('%s <fg=yellow>%s</fg>', 'Updating' if mkdocs_yml.exists() else 'Generating new', mkdocs_yml)
      mkdocs_yml.write_text(yaml.dump(mkdocs_config))


class RepositoryDetails(t.NamedTuple):
  root: Path
  url: str
  branch: str


def get_repository_details(path: Path) -> RepositoryDetails | None:
  from nr.util.git import Git
  git = Git(path)
  if not (toplevel := git.get_toplevel()):
    return None
  remote = next(iter(git.remotes()), None)
  if not remote:
    return None
  url = remote.fetch
  if url.startswith('git@'):
    url = 'https://' + url[4:].replace(':', '/')
  url = url.removesuffix('.git')
  return RepositoryDetails(Path(toplevel), url, git.get_current_branch_name())
