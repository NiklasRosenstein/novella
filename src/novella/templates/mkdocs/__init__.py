
from __future__ import annotations

import dataclasses
import logging
import os
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
      # TODO (@NiklasRosenstein): Sanitize the Markdown header in the same way as Mkdocs.
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
  """ A template to bootstrap an Mkdocs build using Novella. It will set up actions to copy files from the
  {@attr content_directory} and the `mkdocs.yml` config relative to the Novella configuration file (if the
  configuration file exists). Then, unless {@attr apply_default_config} is disabled, it will apply a default
  configuration that is delivered alongside the template (using the Mkdocs-material theme and enabling a
  bunch of Markdown extensions), and then run Mkdocs to either serve or build the documentation.

  The generated action names are `mkdocs-copy-files`, `mkdocs-apply-default` and `mkdocs-run`.

  __Example__

  ```py
  template "mkdocs" {
    content_directory = "docs"
  }

  do "my-preprocessor" before: "mkdocs-run" {
    # ...
  }
  ```
  """

  #: The directory that contains the Mkdocs context.
  content_directory: str = 'content'

  #: The site name to put into the Mkdocs.yml if #apply_default_config is enabled and the site name
  #: is not already set in your own configuration.
  site_name: str | None = None

  #: Apply the default Mkdocs configuration provided alongside this template. Enabled by default.
  apply_default_config: bool = True

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site_dir", "d", description='Build directory for Mkdocs (defaults to "_site")', default="_site")

    def configure_copy_files(copy_files):
      copy_files.paths = [ self.content_directory ]
      if (context.project_directory / 'mkdocs.yml').exists():
        copy_files.paths.append('mkdocs.yml')
    context.do('copy-files', configure_copy_files, name='mkdocs-copy-files')

    def configure_apply_default(apply_default: MkdocsApplyDefaultAction):
      apply_default.site_name = self.site_name
    if self.apply_default_config:
      context.do('mkdocs-apply-default', configure_apply_default, name='mkdocs-apply-default')

    def configure_preprocess_markdown(preprocessor: MarkdownPreprocessorAction):
      preprocessor.use('cat')
      def configure_anchor(anchor: AnchorTagProcessor):
        anchor.renderer = MkdocsMkdocsAnchorAndLinkRenderer(lambda: self.content_directory)
      preprocessor.use('anchor', configure_anchor)
    context.do('preprocess-markdown', configure_preprocess_markdown)

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        context.enable_file_watching()
        run.flags = ActionSemantics.HAS_INTERNAL_RELOADER
        run.args += [ "serve" ]
      else:
        run.args += [ "build", "-d", context.project_directory / context.options.get("site_dir") ]
    context.do('run', configure_run, name='mkdocs-run')


class MkdocsApplyDefaultAction(Action):

  _DEFAULT = Path(__file__).parent / 'mkdocs.yml'

  site_name: str | None = None

  def execute(self) -> None:
    import yaml
    mkdocs_yml = self.novella.build.directory / 'mkdocs.yml'
    if mkdocs_yml.exists():
      mkdocs_config = yaml.safe_load(mkdocs_yml.read_text())
      logger.info('Updating <path>%s</path>', mkdocs_yml)
    else:
      mkdocs_config = {}
      logger.info('Creating <path>%s</path>', mkdocs_yml)

    default_config = yaml.safe_load(self._DEFAULT.read_text())
    if self.site_name:
      default_config['site_name'] = self.site_name

    for key in default_config:
      if key not in mkdocs_config:
        mkdocs_config[key] = default_config[key]

    mkdocs_yml.write_text(yaml.dump(mkdocs_config))
