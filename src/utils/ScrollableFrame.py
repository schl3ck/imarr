import tkinter as tk
from math import copysign
from tkinter import ttk
from typing import Type, Union

from src.utils.constants import padding


class ScrollableFrame(tk.Frame):
  def __init__(
    self,
    master: tk.Frame,
    innerFrame: Type[Union[tk.Frame, ttk.Frame]],
    width=100,
    height=100,
    **kwargs
  ):
    super().__init__(master, **kwargs)
    self.master = master

    self.scrollY = tk.Scrollbar(self)
    self.scrollY.pack(side="right", fill="y")

    self.canvas = tk.Canvas(
      self, height=height, width=width, yscrollcommand=self.scrollY.set,
      highlightthickness=0
    )
    self.canvas.pack(side="left", expand=True, fill="both")
    self.canvas.bind("<Configure>", self.configure)

    self.scrollY["command"] = self.canvas.yview

    self.innerFrame = innerFrame(self.canvas)
    self.innerFrame.pack(side="top", pady=padding)

    self.bind("<Enter>", self.bindMouseWheel)
    self.bind("<Leave>", self.unbindMouseWheel)

    self.canvas.create_window((0, 0),
                              window=self.innerFrame,
                              anchor="nw")

  def configure(self, event):
    self.canvas["scrollregion"] = self.canvas.bbox("all")

  def mouseWheel(self, event):
    self.canvas.yview_scroll(int(copysign(1, event.delta)) * -1, "units")

  def bindMouseWheel(self, event):
    # assume that everything is up to date
    innerHeight = self.innerFrame.winfo_height()
    outerHeight = self.winfo_height()
    if innerHeight > outerHeight:
      self.canvas.bind_all("<MouseWheel>", self.mouseWheel)

  def unbindMouseWheel(self, event):
    self.canvas.unbind_all("<MouseWheel>")
