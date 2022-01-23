
import dataclasses
from docspec import ApiObject, Module
from pydoc_markdown.contrib.processors.smart import SmartProcessor as _SmartProcessor
from novella.api import DocstringProcessor
from novella.context import Context


@dataclasses.dataclass
class SmartProcessor(DocstringProcessor, _SmartProcessor):

  def process_docstring(self, context: Context, obj: ApiObject) -> None:
    module = Module('?placeholder', None, None, [obj])
    self.process([module], None)
