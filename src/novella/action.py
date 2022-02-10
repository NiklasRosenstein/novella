
from __future__ import annotations

import abc
import typing as t

if t.TYPE_CHECKING:
  from .novella import Novella


class Action(abc.ABC):
  """ Base class for actions that can be embedded in a Novella pipeline. """

  novella: Novella

  @abc.abstractmethod
  def execute(self) -> None: ...
