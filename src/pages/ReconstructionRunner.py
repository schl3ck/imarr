from functools import partial
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, List, Tuple, Type, Union
from threading import Thread

from src.pages.BasePage import BasePage
from src.utils.utils import ensureOnScreen
from src.models.dummy import Model
from src.utils.State import State
from src.utils.constants import (padding)
from src.utils.ReactiveVariable import ReactiveVariable

runningModels: List["RunningModel"] = []
reconstructionRunnerVisible = {"value": False}


class RunningModel:
  model: Type[Model] = None
  instance: Model = None
  lastStatus: str = None
  lastProgress: float = None
  finished: ReactiveVariable = None
  running: ReactiveVariable = None
  ranOnce = False
  error: str = None
  thread: Thread = None

  frame: ttk.Labelframe = None
  startCancelButton: ttk.Button = None
  showResultButton: ttk.Button = None
  statusProgressbar: ttk.Progressbar = None
  statusLabel: ttk.Label = None

  def __init__(self, model: Type[Model]):
    self.model = model
    self.instance = model()

    self.finished = ReactiveVariable(value=False)
    self.running = ReactiveVariable(value=False)

    self.finished.registerListener(self.onFinishChanged)
    self.running.registerListener(self.onRunningChanged)
    self.finished.set(False)
    self.running.set(False)

  def run(
    self,
    state: State,
    statusCallback: Callable[["RunningModel", float, str], None],
    doneCallback: Callable[["RunningModel"], None],
    errorCallback: Callable[["RunningModel", str], None]
  ):
    if self.instance.canRun() != True:
      return
    self.ranOnce = True
    self.finished.set(False)
    self.running.set(True)
    self.statusLabel["text"] = "Starting..."
    self.thread = Thread(
      target=self.instance.run,
      args=(
        state.copy(),
        partial(self.onStatus, statusCallback),
        partial(self.onDone, doneCallback),
        partial(self.onError, errorCallback)
      ),
      daemon=True
    )
    self.thread.start()

  def onStatus(
    self,
    statusCallback: Callable[["RunningModel", float, str], None],
    progress: float,
    status: str
  ):
    self.lastProgress = progress
    self.lastStatus = status
    if self.frame:
      if isinstance(progress, float):
        self.statusProgressbar.configure(
          mode="determinate", value=self.lastProgress
        )
      else:
        self.statusProgressbar["mode"] = "indeterminate"
      self.statusLabel["text"] = status
    if statusCallback:
      statusCallback(self, progress, status)

  def onDone(self, doneCallback: Callable[["RunningModel"], None]):
    self.running.set(False)
    self.finished.set(True)
    doneCallback(self)

  def onError(
    self,
    errorCallback: Callable[["RunningModel", str], None],
    errorDescription: str
  ):
    print(errorDescription)
    self.error = errorDescription
    self.running.set(False)
    errorCallback(self, errorDescription)

  def cancel(self):
    self.instance.cancel()
    self.running.set(False)

  def __eq__(self, other: Union["RunningModel", Model]) -> bool:
    return self.model == other.model

  def prepareStart(
    self,
    callback: Callable[["RunningModel"],
                       Tuple[State,
                             Callable[["RunningModel", float, str], None],
                             Callable[["RunningModel"], None],
                             Callable[["RunningModel", str], None]]]
  ):
    if self.running.get():
      self.cancel()
    else:
      args = callback(self)
      self.run(*args)

  def showResults(self, callback):
    args = callback(self)
    self.instance.showResults(*args)

  def showSettings(self, callback):
    args = callback(self)
    self.instance.showSettings(*args)

  def createFrame(
    self,
    master: tk.Frame,
    onStart: Callable[["RunningModel"],
                      Tuple[State,
                            Callable[["RunningModel", float, str], None],
                            Callable[["RunningModel"], None],
                            Callable[["RunningModel", str], None]]],
    onShowResult: Callable[["RunningModel"], tk.Toplevel],
    onShowSettings: Callable[["RunningModel"], tk.Toplevel]
  ):
    self.frame = ttk.Labelframe(master, text=self.model.name)
    self.statusLabel = ttk.Label(
      self.frame,
      text=self.lastStatus or "Running" if self.running.get() else
      ("Done!" if self.finished.get() else self.error or "Ready"),
      wraplength=280
    )
    self.statusProgressbar = ttk.Progressbar(
      self.frame, maximum=1.0, orient=tk.HORIZONTAL
    )
    if self.running.get():
      if isinstance(self.lastProgress, float):
        self.statusProgressbar.configure(
          mode="determinate", value=self.lastProgress
        )
      else:
        self.statusProgressbar["mode"] = "indeterminate"
      self.updateIndeterminateProgress()
    buttonFrame = ttk.Frame(self.frame)
    self.startCancelButton = ttk.Button(
      buttonFrame, text="Start", command=partial(self.prepareStart, onStart)
    )
    self.showResultButton = ttk.Button(
      buttonFrame,
      text="Show result",
      command=partial(self.showResults, onShowResult),
      state="normal" if self.instance.hasResults else "disabled"
    )
    if self.model.hasSettings:
      settings = ttk.Button(
        buttonFrame,
        text="Settings",
        command=partial(self.showSettings, onShowSettings)
      )
    else:
      settings = None

    self.frame.grid_columnconfigure(1, minsize=280)
    self.statusLabel.grid(
      column=1, row=1, padx=padding, pady=padding, sticky="we"
    )
    self.statusProgressbar.grid(column=1, row=2, padx=padding, sticky="we")
    buttonFrame.grid(
      column=1, row=3, padx=padding - 1, pady=padding, sticky="we"
    )
    self.startCancelButton.pack(side="left", fill="x", expand=True)
    self.showResultButton.pack(side="left", fill="x", expand=True)
    if settings:
      settings.pack(side="left", fill="x", expand=True)

    # update labels to reflect current state
    # self.finished.set(self.finished.get())
    # self.running.set(self.running.get())

    canRun = self.instance.canRun()
    if isinstance(canRun, str):
      self.startCancelButton["state"] = "disabled"
      self.statusLabel["text"] = canRun

    return self.frame

  def onFinishChanged(self, value, old=None):
    if self.frame:
      self.showResultButton["state"] = (
        "normal" if self.instance.hasResults else "disabled"
      )
      if value:
        self.statusLabel["text"] = "Done!"
      self.startCancelButton["text"] = "Start"

  def onRunningChanged(self, value, old=None):
    if self.frame:
      self.startCancelButton["text"] = "Cancel" if value else "Start"
      if value:
        self.error = None
        self.frame.after(10, self.updateIndeterminateProgress)
      else:
        self.statusProgressbar["mode"] = "determinate"
        self.statusProgressbar["value"] = 0.
        self.statusLabel["text"] = (
          self.error or ("Canceled!" if self.ranOnce else "Ready")
          if not self.finished.get() else "Done!"
        )

  def updateIndeterminateProgress(self):
    mode = self.statusProgressbar["mode"]
    if self.running.get():
      if (mode == "indeterminate"
          or getattr(mode, "string", None) == "indeterminate"):
        self.statusProgressbar["value"] += 0.01
      self.frame.after(30, self.updateIndeterminateProgress)


class ReconstructionRunner(BasePage):
  def __init__(
    self,
    master: tk.Tk,
    pageHandler: Callable[[str, State], None],
    state: State
  ):
    super().__init__(master)
    self.master = master
    self.pageHandler = pageHandler
    self.state = state

    for model in state.models:
      item = next((m for m in runningModels if m.model.name == model.name),
                  None)
      if item is not None and item.model != model:
        runningModels.remove(item)
        item.cancel()
        item = None
      if item is None:
        item = RunningModel(model)
        runningModels.append(item)
    toRemove = [
      model for model in runningModels
      if model.model not in state.models and not model.ranOnce
    ]
    for model in toRemove:
      runningModels.remove(model)

    self.updateTitle()
    self.createWidgets()
    self.grid(sticky="nsew")
    reconstructionRunnerVisible["value"] = True
    ensureOnScreen(self.master)

  def destroy(self) -> None:
    for model in runningModels:
      model.frame = None
    return super().destroy()

  def updateTitle(self):
    nModels = len([model for model in runningModels if model.running.get()])
    self.master.title(
      "{} Reconstruction{} Running - IMARR".format(
        nModels if nModels > 0 else "No", "" if nModels == 1 else "s"
      )
    )

  def createWidgets(self):
    self.frames = []
    row = 1
    for model in runningModels:
      frame = model.createFrame(
        self, self.onStartModel, self.onShowModelResult, self.onShowSettings
      )
      frame.grid(row=row, column=1, sticky="we", padx=padding, pady=padding)
      row += 1

    self.bBack = ttk.Button(self, text="Back", command=self.goBack)
    self.bBack.grid(row=row, column=1, sticky="we", padx=padding, pady=padding)

  def onStartModel(self, model: RunningModel):
    self.after(50, self.updateTitle)
    return (self.state, self.onStatus, self.onFinished, self.onModelError)

  def onStatus(self, model, progress, status):
    pass

  def onFinished(self, model):
    self.after(50, self.updateTitle)
    # TODO: notify user when not on this page
    pass

  def onModelError(self, model, error):
    self.after(50, self.updateTitle)
    # TODO: notify user when not on this page
    pass

  def onShowModelResult(self, model: RunningModel):
    toplevel = tk.Toplevel(self.master)
    toplevel.focus_set()
    return (toplevel, )

  def onShowSettings(self, model: RunningModel):
    toplevel = tk.Toplevel(self.master)
    toplevel.focus_set()
    return (toplevel, self.state.copy())

  def goBack(self):
    self.pageHandler("back", self.state)

  def buildState(self):
    return self.state

  @staticmethod
  def stateSufficient(state: State):
    needed = [
      "observatory",
      "startDate",
      "endDate",
      "datasets",
      "selectedVars",
      "datasetCDFInstances",
      "selectionStart",
      "selectionEnd",
      "models"
    ]
    return all(state.has(i) for i in needed)
