
from __future__ import annotations

import abc
import re
import dataclasses
import hashlib
import importlib
import typing as t
import typing_extensions as te
from pathlib import Path

from novella.action import Action
from novella.build import BuildContext
from novella.graph import Graph, Node
from novella.novella import NovellaContext

_Closure: te.TypeAlias = 't.Callable[[MarkdownPreprocessor], t.Any]'


@dataclasses.dataclass
class MarkdownFile:
  """ Represents a Markdown file and its contents, to be processed by #MarkdownPreprocessor#s. """

  #: The path to the file. This will point to the file in the project directory, _not_ in the build directory.
  path: Path

  #: The path where the file will be written to. Basically the same as #path but points inside the buil directory.
  output_path: Path

  #: The content to be preprocessed.
  content: str

  #: An alternative filename that serves as the "source path" where the content is loaded from. This may be
  #: different for example in case of the `@cat` tag when it preprocesses the contents of a file to be included.
  source_path: Path | None = None

  def __post_init__(self) -> None:
    self._hash = hashlib.md5(self.content.encode()).hexdigest()

  def changed(self) -> bool:
    return hashlib.md5(self.content.encode()).hexdigest() != self._hash


class MarkdownFiles(t.List[MarkdownFile]):

  def __init__(self, files: t.Iterable[MarkdownFile], context: NovellaContext, build: BuildContext) -> None:
    super().__init__(files)
    self.context = context
    self.build = build


class MarkdownPreprocessorAction(Action):
  """ An action to preprocess Markdown files. All functionality of the processor is implemented by plugins that
  implement the #MarkdownPreprocessor interface. The order of execution of the processors is based on their
  dependencies, much like when #Action#s are executed.

  As a final step, the processor will process escaped inline tags (i.e. replacing `\{@` with `@{`).
  """

  #: The path to the folder in which markdown files should be preprocessed. If this is not set,
  #: all Markdown files in the build directory will be preprocessed.
  path: str | None = None

  #: The encoding to read and write files as.
  encoding: str | None = None

  def __post_init__(self) -> None:
    self._processors = Graph[MarkdownPreprocessor]()
    self.use('shell')
    self.use('cat')
    self.use('anchor')

  def use(
    self,
    processor: str | MarkdownPreprocessor,
    closure: _Closure | None = None,
    name: str | None = None,
  ) -> None:
    """ Register a processor for use in the plugin. """

    from nr.util.plugins import load_entrypoint, NoSuchEntrypointError

    if isinstance(processor, str):
      name = name or processor
      try:
        processor_cls = load_entrypoint(MarkdownPreprocessor, processor)  # type: ignore
        name = name or processor
      except NoSuchEntrypointError:
        module_name, class_name = processor.rpartition('.')[::2]
        module = importlib.import_module(module_name)
        processor_cls = getattr(module, class_name)
      processor = processor_cls(self, name)
    else:
      if not isinstance(processor, MarkdownPreprocessor):
        raise TypeError(f'expected MarkdownProcessor, got {type(processor).__name__}')
      if name is not None and name != processor.name:
        raise RuntimeError('mismatching "name": {name!r} != {processor.name!r}')

    self._processors.add_node(processor, self._processors.last_node_added)

    if closure:
      closure(processor)

  def preprocessor(self, processor_name: str, closure: _Closure | None = None) -> MarkdownPreprocessor:
    """ Access or reconfigure a markdown processor that is already registered. """

    processor = self._processors.nodes[processor_name]
    if closure is not None:
      closure(processor)
    return processor

  def repeat(self, path: Path, output_path: Path, content: str, source_path: Path | None = None, last_processor: MarkdownPreprocessor | None = None) -> str:
    """ Repeat all processors that have been processed so far on the given files. This is used by the `@cat`
    preprocessor to apply all preprocessors previously run on the newly included content. This does not include
    the processor that this method is called from, but only the preprocessors that preceded it. The caller may
    pass itself to the *last_processor* argument to include themselves. """

    files = MarkdownFiles([MarkdownFile(path, output_path, content, source_path)], self.context, self._build)
    for processor in self._past_processors:
      processor.process_files(files)
    if last_processor:
      last_processor.process_files(files)

    return files[0].content

  # Action

  def execute(self, build: BuildContext) -> None:
    """ Execute the preprocessor on all Markdown files specified in #path. """

    from nr.util.fs import recurse_directory

    root = build.directory / self.path if self.path else build.directory
    files = MarkdownFiles([], self.context, build)

    for path in recurse_directory(root):
      assert path.is_absolute(), path
      if path.suffix == '.md':
        files.append(MarkdownFile(
          path=self.context.project_directory / path.relative_to(build.directory),
          output_path=path,
          content=path.read_text(self.encoding),
        ))

    def _commit_files() -> None:
      for file in files:
        if file.changed():
          file.output_path.write_text(file.content, self.encoding)

    for preprocessor in self._processors.nodes.values():
      preprocessor.setup()

    self._build = build
    self._past_processors: list[MarkdownPreprocessor] = []
    for preprocessor in self._processors.execution_order():
      build.notify(self, f'preprocess ({preprocessor.name})', _commit_files)
      preprocessor.process_files(files)
      self._past_processors.append(preprocessor)
    del self._build
    del self._past_processors

    for file in files:
      # Correct escaped inline tags.
      # NOTE (@NiklasRosenstein): This is a bit hacky.. maybe we can find a better place in the code to do this.
      file.content = re.sub(r'(?<!\\)\\\{@', '{@', file.content)
      file.content = re.sub(r'^\\@', '@', file.content, flags=re.M)

    _commit_files()


class MarkdownPreprocessor(Node['MarkdownPreprocessor']):
  """ Interface for plugins to process markdown files. """

  #: The entrypoint under which preprocessor plugins must be registered.
  ENTRYPOINT = 'novella.markdown.preprocessors'

  def __init__(self, action: MarkdownPreprocessorAction, name: str) -> None:
    self.action = action
    self.name = name
    self.graph = action._processors
    self.__post_init__()

  def __post_init__(self) -> None:
    pass

  def setup(self) -> None:
    """ Called before the execution order of processors is determined. """

  @abc.abstractmethod
  def process_files(self, files: MarkdownFiles) -> None:
    """ Process the file contents in *files*. """

