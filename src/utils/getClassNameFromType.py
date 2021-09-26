from typing import Type
from src.pages.BasePage import BasePage


def getClassNameFromType(t: Type[BasePage]) -> str:
  if not hasattr(t.__class__, "__name__") or t.__class__.__name__ != "type":
    t = t.__class__
  return t.__module__.split(".")[-1]
