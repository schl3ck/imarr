from matplotlib import pyplot as plt
from typing import Callable, Union
from tkinter import Toplevel
import tkinter as tk
import tkinter.ttk as ttk
from functools import partial
import numpy as np

from src.utils.MatplotlibTkinterIntegration import createPlot
from src.utils.State import State
from src.utils.constants import padding
from .hoyle import Hoyle_phi, Hoyle_theta, Hoyle_tot, Settings, fitting_Hoyle
from .utils import rotation


class Model:
  """
  Gold Hoyle Model
  ===========

  The model after Gold and Hoyle 1960. Improved to use a toroidal geometry by
  Vandas and Romashets 2017.
  """

  # this tells the application which variables are required so that it can
  # disable the model when some variables are missing
  # for a list of variables have a look at `src/utils/constants.py`
  # "requiredVariables" and "optionalVariables"
  requiredVariables = ["Magnetic Field"]

  # the name of this model
  name = "Gold Hoyle"

  # set to True when this reconstruction has some options to configure
  hasSettings = False

  # set to True when this reconstruction can show some results
  hasResults = False

  def __init__(self):
    self.canceled = False

  def canRun(self) -> Union[bool, str]:
    """
    If the reconstruction model depends on certain packages, check for them
    here if they are installed. Return True only when the model can be run,
    otherwise return a string that describes the problem
    """
    return True

  def showSettings(self, window: Toplevel, state: State):
    """Called when the user wants to change some options"""
    print("showing settings")
    window.title(self.name)

  def run(
    self,
    state: State,
    statusCallback: Callable[[float, str], None],
    doneCallback: Callable[[], None],
    errorCallback: Callable[[str], None]
  ):
    """
    Called when the user wants to run the reconstruction. This function is
    called in a new thread, so it doesn't block the tk mainloop.

    NOTE: You can get the data via `state.getData("mag", "x")`. This data might
    contain NaNs. The reconstruction should be able to handle them.

    Parameters:

    state -- The state object containing all the user inputs. Defined in
    `src/utils/State.py`

    statusCallback -- A function that updates the progress display of the
    reconstruction. The function expects a float between 0 and 1 and a string
    that describes the current operation. If you can't provide the float simply
    pass None instead (not 0, since that would leave the progress bar empty the
    whole time).

    doneCallback -- A function that should be called when the reconstruction
    has finished successfully

    errorCallback -- A function that should be called when the reconstruction
    threw an error. It expects a descriptive string which is directly presented
    to the user.
    """
    self.canceled = False
    try:
      statusCallback(None, "Reading the data")
      # read the magnetic field
      Bx = state.getData("mag", "x")
      By = state.getData("mag", "y")
      Bz = state.getData("mag", "z")
      if Bx is None or By is None or Bz is None:
        raise Exception("Not all magnetic field components found")
      Btotal = state.getData("mag", "total")
      # assume that they all have the same length
      self.r = r = np.linspace(-1, 1, len(Bx))
      self.Bx, self.By, self.Bz = Bx, By, Bz
      statusCallback(None, "Calculating")
      self.result = fitting_Hoyle(
        Bx,
        By,
        Bz,
        Btotal,
        r,
        Settings(),
        statusCallback,
        lambda: self.canceled
      )
      if self.canceled:
        return

      tor = np.pi / 180
      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = self.result.B0 / (1 + self.result.b**2 * (r / self.result.R0)**2)
      # Define Btheta
      Btheta = self.result.B0 * self.result.b * r / (
        (1 + self.result.b**2 * (r / self.result.R0)**2) * (
          self.result.R0 +
          (r / self.result.R0) * np.cos(self.result.theta * tor)
        )
      )
      self.Br, self.Bphi, self.Btheta = rotation(
        Br,
        Bphi,
        Btheta,
        self.result.theta,
        self.result.phi
      )

      self.hasResults = True
      doneCallback()
    except Exception as e:
      self.hasResults = False
      errorCallback(e)
      raise

  def cancel(self):
    self.canceled = True

  def showResults(self, window: Toplevel):
    """Called when the user wants to see the results"""
    window.title(self.name)
    self.resultsWindow = window
    items = [
      ("Magnetic field error (quality)", "magFieldError", "%"),
      ("B0", "B0", "nT"),
      "b",
      ("R0", "R0", "AU"),
      "phi",
      "theta"
    ]
    for i, item in enumerate(items):
      unit = None
      if isinstance(item, tuple):
        title = item[0]
        key = item[1]
        if len(item) > 2:
          unit = item[2]
      else:
        title = item
        key = item

      label = ttk.Label(window, text=title)
      label.grid(column=0, row=i, padx=padding, pady=padding)
      var = tk.StringVar(window, str(getattr(self.result, key)))
      entry = ttk.Entry(window, state="readonly", textvariable=var)
      entry.var = var
      entry.grid(column=1, row=i, padx=padding, pady=padding)
      colMostRight = 1
      if hasattr(self.result, key + "Error"):
        label2 = ttk.Label(window, text="+-")
        label2.grid(column=2, row=i)
        var2 = tk.StringVar(window, str(getattr(self.result, key + "Error")))
        entry2 = ttk.Entry(window, state="readonly", textvariable=var2)
        entry2.var = var2
        entry2.grid(column=3, row=i, padx=padding, pady=padding)
        colMostRight = 3
      if unit:
        label3 = ttk.Label(window, text=unit)
        label3.grid(column=colMostRight + 1, row=i, padx=padding)

    btnFrame = ttk.Frame(window)
    btnFrame.grid(
      column=0,
      row=len(items) + 1,
      columnspan=4,
      sticky="we",
      padx=padding,
      pady=padding
    )
    btn = ttk.Button(btnFrame, text="Show Fit", command=self.showFit)
    btn.grid(column=1, row=1)
    btn = ttk.Button(
      btnFrame,
      text="Show Bphi Plot",
      command=partial(self.showPolar, Hoyle_phi)
    )
    btn.grid(column=2, row=1)
    btn = ttk.Button(
      btnFrame,
      text="Show Btheta Plot",
      command=partial(self.showPolar, Hoyle_theta)
    )
    btn.grid(column=3, row=1)
    btn = ttk.Button(
      btnFrame,
      text="Show Btotal Plot",
      command=partial(self.showPolar, Hoyle_tot)
    )
    btn.grid(column=4, row=1)

  def showFit(self):
    window = tk.Toplevel(self.resultsWindow)
    fig = plt.figure(figsize=(6.4, 8))

    r = self.r
    Bx, By, Bz = self.Bx, self.By, self.Bz
    Br, Bphi, Btheta = self.Br, self.Bphi, self.Btheta

    plt.subplot(411)
    plt.title('Bx')
    plt.ylabel('Amplitude [nT]')
    plt.xlabel('r (normalized)')
    plt.plot(r, Bx, label='In-situ data', c='k')
    plt.plot(r, Br, label='Gold_Hoyle Fit', c='b')

    plt.subplot(412)
    plt.title('By')
    plt.ylabel('Amplitude [nT]')
    plt.xlabel('r (normalized)')
    plt.plot(r, By, label='In-situ data', c='k')
    plt.plot(r, Bphi, label='Gold_Hoyle Fit', c='c')

    plt.subplot(413)
    plt.title('Bz')
    plt.ylabel('Amplitude [nT]')
    plt.xlabel('r (normalized)')
    plt.plot(r, Bz, label='In-situ data', c='k')
    plt.plot(r, Btheta, label='Gold_Hoyle Fit', c='m')

    plt.subplot(414)
    plt.title('Difference modeled - observed')
    plt.ylabel('Amplitude [nT]')
    plt.xlabel('r (normalized)')
    plt.plot(r, Br - Bx, c='b', label="Br - Bx")
    plt.plot(r, Bphi - By, c='c', label="Bphi - By")
    plt.plot(r, Btheta - Bz, c='m', label="Btheta - Bz")
    plt.legend()

    plt.suptitle('Magnetic field')
    plt.subplots_adjust(top=0.91, right=0.96, hspace=0.7)

    self.plotFrame = ttk.Frame(window)
    self.canvas, self.toolbar = createPlot(self.plotFrame, fig)

    self.plotFrame.grid(row=1, column=1, rowspan=3)
    self.toolbar.grid(row=1, column=1, sticky="we")
    self.canvas.get_tk_widget().grid(row=2, column=1)
    window.bind("<Destroy>", lambda x: plt.close(fig))

  def showPolar(self, func):
    window = tk.Toplevel(self.resultsWindow, takefocus=False)
    window.title("Gold-Hoyle result")
    fig = func(self.result.B0, self.result.R0, self.result.b, 200)
    frame = ttk.Frame(window)
    canvas, toolbar = createPlot(frame, fig)
    frame.grid(row=1, column=1)
    toolbar.grid(row=1, column=1, sticky="we")
    canvas.get_tk_widget().grid(row=2, column=1)
    window.bind("<Destroy>", lambda x: plt.close(fig))
