from time import sleep
from src.utils.State import State
from typing import Callable, Union
from tkinter import Frame, Toplevel
from cdflib.cdfread import CDF
from astropy.time import Time
import tkinter as tk
import tkinter.ttk as ttk


class Model:
  """
  Dummy Model
  ===========

  This section should describe the model.
  
  This is a dummy model to test and finalize the model API. It should also
  aid in creating new model implementations.

  This doc string may get a special syntax if there's enough time. Otherwise it
  will be printed in plain text in the application.
  For now, single line breaks between words like this one
  are stripped out even when the previous line ends with a dot or comma.
  """

  # this tells the application which variables are required so that it can
  # disable the model when some variables are missing
  # for a list of variables have a look at `src/utils/constants.py`
  # "requiredVariables" and "optionalVariables"
  requiredVariables = ["Magnetic Field"]

  # the name of this model
  name = "Dummy Model"

  # set to True when this reconstruction has some options to configure
  hasSettings = True

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

    state -- The state object containing all the user inputs and data. Defined
    in `src/utils/State.py`.

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
    statusCallback(0., "Processing...")
    for progress in range(0, 1.1, 0.1):
      if self.canceled:
        return
      statusCallback(progress, "Processing...")
      sleep(1)

    self.hasResults = True
    doneCallback()

  def cancel(self):
    self.canceled = True

  def showResults(self, window: Toplevel):
    """Called when the user wants to see the results"""
    ttk.Label(window, text="The result is: 42").grid(sticky="nsew")
    window.title(self.name)
