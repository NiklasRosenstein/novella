
""" A configurable renderer for Python API documentation. """

import dataclasses
import logging

from docspec import ApiObject, Module
from novella.core.context import Context
from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer, MarkdownReferenceResolver
from ._api import PythonApiRenderer

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DefaultPythonApiRenderer(PythonApiRenderer, MarkdownRenderer):

  render_module_header: bool = False

  def init(self, context: Context) -> None:
    logger.info('init DefaultPythonApiRenderer')

  def render_as_markdown(self, obj: ApiObject) -> str:
    module = Module('?placeholder', None, None, [obj])
    return self.render_to_string([module])
