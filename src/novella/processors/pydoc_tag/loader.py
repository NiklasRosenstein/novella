
import dataclasses
import logging
import os
import sys
import typing as t
from pathlib import Path

import docspec
import docspec_python

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonLoader:
  """ Loads Python module using #docspec_python per its configuration and exposes the loaded modules for consumption
  by other actions. The default configuration will attempt to search for modules in the `src/` directory, if it exists,
  or alternatively in the project root directory. Note that the auto discovery does not work well with Python 3
  namespace packages.

  __lib2to3 Quirks__

  Pydoc-Markdown doesn't execute your Python code but instead relies on the `lib2to3` parser. This means it also
  inherits any quirks of `lib2to3`.

  __List of known quirks__

  * A function argument in Python 3 cannot be called `print` even though it is legal syntax.
  """

  #: A list of module names that this loader will search for and then parse. The modules are searched using the
  #: #sys.path of the current Python interpreter, unless the #search_path option is specified.
  modules: list[str] | None = None

  #: A list of package names that this loader will search for and then parse, including all sub-packages and modules.
  packages: list[str] | None = None

  #: Specify a single module to load.
  module: str | None = None

  #: Specify a single package to load.
  package: str | None = None

  #: The module search path. Defaults to `[ "src/", "." "]`.
  search_path: list[str] = dataclasses.field(default_factory=lambda: ['src', '.'])

  #: Use #sys.path in addition to #search_path.
  use_sys_path: bool = False

  #: List of modules to ignore when using module discovery on the #search_path.
  ignore_when_discovered: list[str] | None = dataclasses.field(default_factory=lambda: ['test', 'tests', 'setup'])

  #: Options for the Python parser.
  parser: docspec_python.ParserOptions = dataclasses.field(default_factory=docspec_python.ParserOptions)

  #: The encoding to use when reading the Python source files.
  encoding: str | None = None

  #: Docstring processors.
  # processors: list[DocstringProcessor] = dataclasses.field(default_factory=_get_default_processors)

  def load_all(self, project_dir: Path) -> list[docspec.Module]:
    return list(self.load(project_dir))

    def _visit(obj: docspec.ApiObject) -> None:
      for processor in self.processors:
        processor.process_docstring(context, obj)

    docspec.visit(self.modules, _visit)

    if not self.modules:
      logger.warning('No modules loaded')

  def get_effective_search_path(self, project_dir: Path) -> list[str]:
    search_path = list(self.search_path)
    if '*' in search_path:
      index = search_path.index('*')
      search_path[index:index+1] = sys.path
    return [os.path.join(project_dir, x) for x in search_path] + (sys.path if self.use_sys_path else [])

  def load(self, project_dir: Path) -> t.Iterable[docspec.Module]:
    search_path = self.get_effective_search_path(project_dir)
    modules = list(self.modules or []) + ([self.module] if self.module else [])
    packages = list(self.packages or []) + ([self.package] if self.package else [])
    do_discover = (self.modules is None and self.packages is None and self.module is None and self.package is None)

    if do_discover:
      for path in search_path:
        try:
          discovered_items = list(docspec_python.discover(path))
        except FileNotFoundError:
          continue

        logger.info(
          'Discovered Python modules %s and packages %s in %r.',
          [x.name for x in discovered_items if isinstance(x, docspec_python.DiscoveryResult.Module)],
          [x.name for x in discovered_items if isinstance(x, docspec_python.DiscoveryResult.Package)],
          path,
        )

        for item in discovered_items:
          if item.name in self.ignore_when_discovered:
            continue
          if isinstance(item, docspec_python.DiscoveryResult.Module):
            modules.append(item.name)
          elif isinstance(item, docspec_python.DiscoveryResult.Package):
            packages.append(item.name)

    logger.info(
      'Load Python modules (search_path: %r, modules: %r, packages: %r, discover: %s)',
      search_path, modules, packages, do_discover
    )

    return docspec_python.load_python_modules(
      modules=modules,
      packages=packages,
      search_path=search_path,
      options=self.parser,
      encoding=self.encoding,
    )
