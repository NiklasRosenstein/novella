
from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from novella.action import Action
from novella.novella import NovellaContext
from novella.template import Template

if t.TYPE_CHECKING:
  from novella.processor import ProcessMarkdownAction
  from novella.processors.pydoc.tag import PydocTagProcessor
  from novella.actions.run import RunAction

logger = logging.getLogger(__name__)


class MkdocsTemplate(Template):
  """ A template to bootstrap a pipeline for processing content for Mkdocs.

  __Example configuration__:

  ```py
  template "mkdocs" {
    content_directory = "docs"
    source_directory = ".."
  }
  ```
  """

  #: The directory that contains the Mkdocs context.
  content_directory: str = 'content'

  #: The source directory that contains the Python source code relative to the Novella build script.
  source_directory: str = '../src'

  #: The module name(s) to load explicitly. If neither this nor {@attr packages} is set, the Python source
  #: code to load will be detected automatically.
  modules: list[str] | None = None

  #: The package name(s) to load explicitly.
  packages: list[str] | None = None

  #: A list of directories that contains Mako templates to load for the `@pydoc` processor. Use this if you
  #: want to override custom templates.
  template_directories: list[str] = []

  #: Options for the `@pydoc` processor.
  options: dict[str, t.Any] = {}

  #: Apply the default Mkdocs configuration provided alongside this template. Enabled by default.
  apply_default_config: bool = True

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site_dir", "d", description="Build directory for Mkdocs (not with --serve)", default="_site")

    def configure_copy_files(copy_files):
      copy_files.paths = [ self.content_directory ]
      if (context.project_directory / 'mkdocs.yml').exists():
        copy_files.paths.append('mkdocs.yml')
    context.do('copy-files', configure_copy_files)

    if self.apply_default_config:
      context.do('mkdocs-apply-default')

    def configure_process_markdown(process_markdown: ProcessMarkdownAction):
      def configure_pydoc(pydoc: PydocTagProcessor):
        pydoc.loader.search_path = [ context.project_directory / self.source_directory ]
        pydoc.loader.modules = self.modules
        pydoc.loader.packages = self.packages
        pydoc.template_directories = self.template_directories
        pydoc.options.update(self.options)
      process_markdown.use('pydoc', configure_pydoc)
      process_markdown.use('cat')
    context.do('process-markdown', configure_process_markdown)

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        run.args += [ "serve" ]
      else:
        run.args += [ "build", "-d", context.project_directory / context.options.get("site_dir") ]
    context.do('run', configure_run)


class MkdocsApplyDefaultAction(Action):

  _DEFAULT = Path(__file__).parent / 'mkdocs.yml'

  def execute(self) -> None:
    import yaml
    mkdocs_yml = self.novella.build_directory / 'mkdocs.yml'
    if mkdocs_yml.exists():
      mkdocs_config = yaml.safe_load(mkdocs_yml.read_text())
      logger.info('  Updating <path>%s</path>', mkdocs_yml)
    else:
      mkdocs_config = {}
      logger.info('  Creating <path>%s</path>', mkdocs_yml)

    default_config = yaml.safe_load(self._DEFAULT.read_text())
    for key in default_config:
      if key not in mkdocs_config:
        mkdocs_config[key] = default_config[key]

    mkdocs_yml.write_text(yaml.dump(mkdocs_config))
