
from __future__ import annotations

import typing as t

from novella.novella import NovellaContext
from novella.template import Template

if t.TYPE_CHECKING:
  from novella.processor import ProcessMarkdownAction
  from novella.processors.pydoc_tag.pydoc_tag import PydocProcessor
  from novella.actions.run import RunAction


class MkdocsTemplate(Template):

  #: The directory that contains the Mkdocs context.
  content_directory: str = 'content'

  #: The source directory that contains the Python source code relative to the Novella build script.
  source_directory: str = '../src'

  #: The module name(s) to load explicitly. If neither this nor {@attr packages} is set, the Python source
  #: code to load will be detected automatically.
  modules: list[str] | None = None

  #: THe package name(s) to load explicitly.
  packages: list[str] | None = None

  #: A list of directories that contains Mako templates to load for the `@pydoc` processor. Use this if you
  #: want to override custom templates.
  template_directories: list[str] = []

  #: Options for the `@pydoc` processor.
  options: dict[str, t.Any] = {}

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("serve", description="Use mkdocs serve", flag=True)
    context.option("site_dir", "d", description="Build directory for Mkdocs (not with --serve)", default="_site")

    def configure_copy_files(copy_files):
      copy_files.paths = [ 'content', 'mkdocs.yml' ]
    context.do('copy-files', configure_copy_files)

    def configure_process_markdown(process_markdown: ProcessMarkdownAction):
      def configure_pydoc(pydoc: PydocProcessor):
        pydoc.loader.search_path = [ context.project_directory / self.source_directory ]
        pydoc.loader.modules = self.modules
        pydoc.loader.packages = self.packages
        pydoc.template_directories = self.template_directories
        pydoc.options.update(self.options)
      process_markdown.use('pydoc', configure_pydoc)
    context.do('process-markdown', configure_process_markdown)

    def configure_run(run: RunAction) -> None:
      run.args = [ "mkdocs" ]
      if context.options.get("serve"):
        run.args += [ "serve" ]
      else:
        run.args += [ "build", "-d", context.project_directory / context.options.get("site_dir") ]
    context.do('run', configure_run)
