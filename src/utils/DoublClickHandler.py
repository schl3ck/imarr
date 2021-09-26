import tkinter as tk
from typing import Any, Callable
from datetime import datetime
from src.utils.constants import doubleClickTime

class DoubleClickHandler:
  def __init__(
    self,
    widget: tk.BaseWidget,
    customEventName: str = None,
    onSingleClick: Callable[[], None] = None,
    onDoubleClick: Callable[[], None] = None,
    requiresSingleForDouble: bool = False
  ) -> None:
    self.widget = widget
    self.onSingleClick = onSingleClick
    self.onDoubleClick = onDoubleClick
    self.requiresSingleForDouble = requiresSingleForDouble
    self.hasSingle = None

    if customEventName:
      widget.bind(customEventName, self.single)
      print(f"DoubleClickHandler: bound to {customEventName}")
    else:
      widget.bind("<Button-1>", self.single)
      print("DoubleClickHandler: bound to <Button-1>")
    widget.bind("<Double-Button-1>", self.double)
    print("DoubleClickHandler: bound to <Double-Button-1>")
    # TODO: use this

  def single(self, *args, **kwargs):
    print("DoubleClickHandler: single click")
    self.hasSingle = datetime.now()
    if self.onSingleClick:
      self.onSingleClick(*args, **kwargs)

  def double(self, *args, **kwargs):
    print("DoubleClickHandler: double click")
    if (self.requiresSingleForDouble and
        (datetime.now() - self.hasSingle).total_seconds() > doubleClickTime):
      print("DoubleClickHandler: double click prevented")
      return
    if self.onDoubleClick:
      self.onDoubleClick(*args, **kwargs)
