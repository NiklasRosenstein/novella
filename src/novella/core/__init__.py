
""" A pipeline describes the steps to perform a build of the documentation. """

from .pipeline import Action, Pipeline
from .context import Context
from .actions.process_markdown import MarkdownProcessor

__all__ = [
  'Action',
  'Pipeline',
  'Context',
  'MarkdownProcessor',
]

__version__ = '0.1.0'
