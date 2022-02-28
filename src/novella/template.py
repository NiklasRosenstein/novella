
from __future__ import annotations

import abc
import typing as t

if t.TYPE_CHECKING:
  from novella.novella import NovellaContext


class Template(abc.ABC):
  """ A template represents a codified sequence of actions that can be further customized, with the intent
  to reduce the boilerplate of the `build.novella` file. """

  ENTRYPOINT = 'novella.templates'

  context: NovellaContext

  def __init__(self, context: NovellaContext) -> None:
    self.context = context

  def setup(self, context: NovellaContext) -> None:
    """ Called before the `pre` closure in #NovellaContext.template(). """

    pass

  def define_pipeline(self, context: NovellaContext) -> None:
    """ Called between the `pre` and `post` closure in #NovellaContext.template(). """

    pass
