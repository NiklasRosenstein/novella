
from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from novella.action import Action
from novella.build import BuildContext
from novella.novella import NovellaContext
from novella.template import Template
from .installer import get_installed_hugo_version

if t.TYPE_CHECKING:
  from novella.action import CopyFilesAction, RunAction
  from novella.markdown.preprocessor import MarkdownPreprocessorAction

logger = logging.getLogger(__name__)


class HugoTemplate(Template):

  #: The directory that contains the Hugo documentation source code content. Defaults to `content/`.
  content_directory: str = 'content'

  #: The directory that contains all the Hugo content. This directory should contain the #content_directory.
  #: Defaults to `./`, i.e. the same directory where the Novella build file is located. All files in this
  #: directory except for the #content_directory will be linked into the build directory.
  hugo_directory: str = '.'

  def define_pipeline(self, context: NovellaContext) -> None:
    context.option("server", description="Use `hugo server` (deprecated; use --serve instead)", flag=True)
    context.option("serve", description="Use `hugo server`", flag=True)
    context.option("port", description="The port to serve under", default="8000")
    context.option("base-url", description='Hugo baseURL')
    context.option("site-dir", description='Build directory for Hugo (defaults to "_site")', default="_site")
    context.option("drafts", description='Build drafts.', flag=True)

    # TODO (@NiklasRosenstein): Can we instead link or use Copy-on-Write for all non-Markdown files, or everything
    #   except the conten_directory?
    copy_files = t.cast('CopyFilesAction', context.do('copy-files'))
    copy_files.paths = [self.hugo_directory]

    preprocessor = t.cast('MarkdownPreprocessorAction', context.do('preprocess-markdown', name='preprocess-markdown'))
    preprocessor.path = str(Path(self.hugo_directory) / self.content_directory)

    installed_hugo_version = get_installed_hugo_version()
    if installed_hugo_version:
      get_hugo_bin = lambda: "hugo"
      logger.info("Using %s (already installed)", installed_hugo_version)
    else:
      installer = t.cast(InstallHugoAction, context.do(InstallHugoAction(context, 'install-hugo')))
      get_hugo_bin = lambda: str(installer.path)

    def configure_run(run: RunAction) -> None:
      run.args = [ get_hugo_bin() ]
      if base_url := context.options.get('base-url'):
        run.args += ['-b', t.cast(str, base_url)]
      if context.options["server"] or context.options["serve"]:
        port = int(str(context.options["port"]))
        run.supports_reloading = True
        run.args += [ "server", "--port", str(port) ]
      else:
        run.args += [ "-d", context.project_directory / str(context.options["site-dir"]) ]
      if context.options.get("drafts"):
        run.args += ["--buildDrafts"]
    context.do('run', configure_run, name='hugo-run')


class InstallHugoAction(Action):
  """ Action to install Hugo into the build directory if it is not available on the system. """

  def setup(self, build: BuildContext) -> None:
    self.path = build.directory / '.tmp' / 'hugo'
    self.version: str | None = None
    self.extended = True

  def execute(self, build: BuildContext) -> None:
    from .installer import install_hugo
    logger.info('Installing Hugo to <fg=yellow>%s</fg>', self.path)
    install_hugo(str(self.path), self.version, self.extended)
