from typing import Any, Callable, Generic, List, TypeVar

T = TypeVar("T")
Listener = Callable[[T], None]


class ReactiveVariable(Generic[T]):
  value: T = None
  _listeners = None

  def __init__(self, value: T = None, listeners: List[Listener] = None):
    self.value = value
    self._listeners = []
    try:
      self._listeners.extend(listeners)
    except:
      pass

  def set(self, value: T):
    for listener in self._listeners:
      listener(value, old=self.value)
    self.value = value

  def get(self) -> T:
    return self.value

  def registerListener(self, *listeners: List[Listener]):
    """Registers one or multiple callback functions to be called when the
    variable changes.

    The listener is called like `listener(value, old=oldValue)`
    """
    self._listeners.extend([arg for arg in listeners if callable(arg)])

  def removeListener(self, *listeners: List[Listener]):
    """Removes one or multiple listeners from this variable. Provide the
    original function.
    """
    for arg in listeners:
      try:
        self._listeners.remove(arg)
      except ValueError:
        pass
