
from __future__ import annotations

import abc
import dataclasses
import hashlib
import importlib
import typing as t
from pathlib import Path

from novella.action import Action
from novella.build import BuildContext
from novella.novella import Novella, NovellaContext

_Closure: t.TypeAlias = 't.Callable[[MarkdownPreprocessor], t.Any]'


@dataclasses.dataclass
class MarkdownFile:
  path: Path
  content: str

  def __post_init__(self) -> None:
    self._hash = hashlib.md5(self.content.encode()).hexdigest()

  def changed(self) -> bool:
    return hashlib.md5(self.content.encode()).hexdigest() != self._hash


class MarkdownFiles(list[MarkdownFile]):

  def __init__(self, files: t.Iterable[MarkdownFile], context: NovellaContext, build: BuildContext) -> None:
    super().__init__(files)
    self.context = context
    self.build = build


class MarkdownPreprocessorAction(Action):
  """ Pre-processor for Markdown files. """

  #: The path to the folder in which markdown files should be preprocessed. If this is not set,
  #: all Markdown files in the build directory will be preprocessed.
  path: Path | None = None

  #: The encoding to read and write files as.
  encoding: str | None = None

  def __post_init__(self) -> None:
    self._pipeline: list[MarkdownPreprocessor] = []
    self._processors: dict[str, MarkdownPreprocessor] = {}

  def execute(self, build: BuildContext) -> None:
    from nr.util.fs import recurse_directory
    root = self.path or build.directory
    files = MarkdownFiles([], self.context, build)

    for path in recurse_directory(root):
      if path.suffix == '.md':
        files.append(MarkdownFile(path.relative_to(root), path.read_text(self.encoding)))

    def _commit_files() -> None:
      for file in files:
        if file.changed():
          (root / file.path).write_text(file.content, self.encoding)

    for preprocessor in self._pipeline:
      name = next((k for k, v in self._processors.items() if v is preprocessor), None)
      if name:
        build.notify(self, f'preprocess ({name})', _commit_files)
      preprocessor.process_files(files)

    for file in files:
      # Correct escaped inline tags.
      # NOTE (@NiklasRosenstein): This is a bit hacky.. maybe we can find a better place in the code to do this.
      file.content = file.content.replace('\\{@', '{@')

    _commit_files()

  def use(
    self,
    processor: str | MarkdownPreprocessor,
    closure: _Closure | None = None,
    name: str | None = None,
    before: str | None = None,
    head: bool = False,
  ) -> None:
    """ Register a processor for use in the plugin. """

    from nr.util.plugins import load_entrypoint, NoSuchEntrypointError

    if head and before is not None:
      raise ValueError('arguments "head" and "before" cannot be used at the same time')

    if isinstance(processor, str):
      try:
        processor_cls = load_entrypoint(MarkdownPreprocessor, processor)  # type: ignore
        name = name or processor
      except NoSuchEntrypointError:
        module_name, class_name = processor.rpartition('.')[::2]
        module = importlib.import_module(module_name)
        processor_cls = getattr(module, class_name)
        name = name or class_name
      processor = processor_cls()

    if not isinstance(processor, MarkdownPreprocessor):
      raise TypeError(f'expected MarkdownProcessor, got {type(processor).__name__}')

    if head:
      insert_index = 0
    elif before is not None:
      insert_index = self._pipeline.index(self._processors[before])
    else:
      insert_index = len(self._pipeline)

    if closure:
      closure(processor)

    self._pipeline.insert(insert_index, processor)
    if name is not None:
      self._processors[name] = processor

  def preprocessor(self, processor_name: str, closure: _Closure | None = None) -> MarkdownPreprocessor:
    """ Access or reconfigure a markdown processor that is already registered. """

    processor = self._processors[processor_name]
    if closure is not None:
      closure(processor)
    return processor


class MarkdownPreprocessor(abc.ABC):
  """ Interface for plugins to process markdown files. """

  ENTRYPOINT = 'novella.markdown.preprocessors'

  @abc.abstractmethod
  def process_files(self, files: MarkdownFiles) -> None: ...
