from typing import Union
import tkinter as tk
import tkinter.ttk as ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
  FigureCanvasTkAgg, NavigationToolbar2Tk
)
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler


def createPlot(master: Union[tk.Frame, ttk.Frame], fig: Figure, canvasMaster: Union[tk.Frame, ttk.Frame]=None):
  """Creates the plot canvas and connects the toolbar to it.
  You have to place the canvas and toolbar yourself via `.pack()` or `.grid()`.
  To place the canvas call `canvas.get_tk_widget().pack()`
  """
  canvas = FigureCanvasTkAgg(fig, master=canvasMaster or master)
  canvas.draw()
  canvas.mpl_connect("key_press_event", key_press_handler)

  toolbar = NavigationToolbar2Tk(canvas, master, pack_toolbar=False)
  toolbar.update()

  return canvas, toolbar
