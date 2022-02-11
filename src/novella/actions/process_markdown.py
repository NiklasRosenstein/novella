
import logging
import typing as t

from nr.util import proxy
from nr.util.fs import recurse_directory
from nr.util.plugins import PluginRegistry, load_entrypoint

from novella.action import Action
from novella.processor import ENTRYPOINT, MarkdownProcessor, plugin_registry

logger = logging.getLogger(__name__)


class ProcessMarkdownAction(Action):
  """ An action to process all Markdown files in the given directory with a given list of processor plugins. """

  def __init__(self) -> None:
    self._processors: list[MarkdownProcessor] = []
    self.directory: str = '.'

  def use(self, processor_name: str, closure: t.Callable | None = None) -> None:
    """ Add a markdown processor to use. The *processor_name* can be the name of an entry point registered under
    the `ENTRYPOINT` group or a relative path in the project directory pointing to a Python file that will be loaded
    and can register plugins. """

    if '/' in processor_name:
      if closure is not None:
        raise RuntimeError(f'closure is not supported for processors loaded from file ({processor_name!r})')
      file = self.novella.project_directory / processor_name
      scope = {'__file__': str(file)}
      plugins = PluginRegistry()
      try:
        proxy.push(plugin_registry, plugins)
        exec(compile(file.read_text(), file, 'exec'), scope)
      finally:
        proxy.pop(plugin_registry)
      for _, processor in plugins.group(MarkdownProcessor, MarkdownProcessor):
        self._processors.append(processor)

    else:
      cls = load_entrypoint(ENTRYPOINT, processor_name)
      assert isinstance(cls, type) and issubclass(cls, MarkdownProcessor), cls
      processor = cls()
      if closure:
        closure(processor)
      self._processors.append(processor)

  def execute(self) -> None:
    for path in recurse_directory(self.novella.build_directory / self.directory):
      if path.suffix == '.md':
        logger.info('Process %s', path)
        for plugin in self._processors:
          plugin.process_markdown(self.novella, path)
