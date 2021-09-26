from functools import partial
import tkinter as tk
from tkinter import filedialog as fd
from tkinter.messagebox import showerror
import json
from typing import Callable, Dict, List, Type
import os.path as path
import re

from src.pages.BasePage import BasePage
from src.pages.ReconstructionRunner import ReconstructionRunner
from src.pages.ReconstructionSelection import ReconstructionSelection
from src.pages.PlotSelection import PlotSelection
from src.pages.DatasetSelection import DatasetSelection
from src.pages.ObservatorySelection import ObservatorySelection
from src.utils.State import State
from src.utils.constants import cacheFolder
from src.utils.getClassNameFromType import getClassNameFromType
from src.utils.utils import isMacOS

recentSessionsFile = cacheFolder + "recentSessions.txt"


class MenuBar(tk.Menu):
  fileMenu: tk.Menu = None
  gotoMenu: tk.Menu = None
  onSessionLoad: Callable[[State], None] = None
  onSessionSave: Callable[[], State] = None
  pageHandler: Callable[[str, State], None] = None
  gotoLabels: List[str] = [
    "Observatory selection",
    "Dataset selection",
    "Plot",
    "Model selection",
    "Running models",
  ]
  pages: List[Type[BasePage]] = [
    ObservatorySelection,
    DatasetSelection,
    PlotSelection,
    ReconstructionSelection,
    ReconstructionRunner
  ]
  currentPage: BasePage = None
  keybindingFuncs: Dict[str, str] = {}
  recentSessions: List[str] = []
  hotkeysRegistered = False
  lastFileName: str = None

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fileMenu = tk.Menu(self, tearoff=False, title="File")
    self.gotoMenu = tk.Menu(self, tearoff=False, title="Go to page")
    self.recentMenu = tk.Menu(
      self.fileMenu, tearoff=False, title="Recent sessions"
    )
    self.add_cascade(label="File", menu=self.fileMenu, underline=0)
    self.add_cascade(label="Go to page", menu=self.gotoMenu, underline=0)

    self.fileMenu.add_command(
      label="Load session", command=self.askLoadSession, underline=0
    )
    self.fileMenu.add_command(
      label="Save session ({}+S)".format("Cmd" if isMacOS() else "Ctrl"),
      command=self.askSaveSession,
      underline=0
    )
    self.fileMenu.add_cascade(
      label="Recent sessions", menu=self.recentMenu, underline=0
    )

    for label, page in zip(self.gotoLabels, self.pages):
      self.gotoMenu.add_command(
        label=label, command=partial(self.goto, getClassNameFromType(page))
      )

    self.readRecentSessions()
    self.populateRecentSessionsMenu()

  def registerHotkeys(self):
    if self.hotkeysRegistered:
      return
    self.keybindingFuncs["save"] = self.master.bind(
      "<{}-s>".format("Command" if isMacOS() else "Control"),
      self.askSaveSession,
      True
    )
    self.fileMenu.entryconfigure(
      1, label="Save session ({}+S)".format("Cmd" if isMacOS() else "Ctrl")
    )
    self.hotkeysRegistered = True

  def unregistHotkeys(self):
    if not self.hotkeysRegistered:
      return
    self.master.unbind(
      "<{}-s>".format("Command" if isMacOS() else "Control"),
      self.keybindingFuncs["save"]
    )
    self.fileMenu.entryconfigure(1, label="Save session")
    self.hotkeysRegistered = False

  def loadSession(self, session: str):
    asDict = dict()
    try:
      with open(session, "r") as file:
        asDict = json.load(file)
    except OSError as e:
      showerror(
        "Error loading session", "Could not load session:\n" + e.strerror
      )
    except AttributeError:
      return
    state = State(asDict, ignoreErrors=False)
    self.onSessionLoad(state)
    self.addRecentSession(session)
    self.lastFileName = path.basename(session)

  def askLoadSession(self):
    if not callable(self.onSessionLoad):
      print("loadSession(): no method provided to onSessionLoad")
      return
    session = fd.askopenfilename(
      defaultextension=".imarr",
      filetypes=(("IMARR Session", "*.imarr"), ("All files", "*")),
      initialdir="./sessions",
      title="Load session"
    )
    self.loadSession(session)

  def askSaveSession(self, event=None):
    if not callable(self.onSessionSave):
      print("saveSession(): no method provided to onSessionSave")
      return
    if self.currentPage.disableSaveHotkey and event is not None:
      return
    state = self.onSessionSave()
    if state is None:
      showerror(
        "Error saving session", "Could not save session:\nNo session available"
      )
    asDict = state.to_dict(True)
    initialFilename = self.lastFileName
    if initialFilename is None:
      initialFilename = ""
      if state.has("observatory"):
        match = re.match(r"^[\w ]+", state.observatory)
        if match:
          initialFilename = match.group(0).strip()
        else:
          initialFilename = state.observatory

      if state.has("startDate"):
        initialFilename += "-"
        match = re.match(r"\d{4}-\d\d-\d\d", state.startDate.value)
        if match:
          initialFilename += match.group(0)
    session = fd.asksaveasfilename(
      confirmoverwrite=True,
      initialdir="./sessions",
      title="Save session",
      filetypes=(("IMARR Session", "*.imarr"), ),
      defaultextension=".imarr",
      initialfile=initialFilename
    )
    if len(session) == 0:
      # user aborted
      return
    try:
      with open(session, "w") as file:
        json.dump(asDict, file, separators=(",", ":"))
    except OSError as e:
      showerror(
        "Error saving session", "Could not save session:\n" + e.strerror
      )
    except AttributeError:
      pass
    finally:
      self.addRecentSession(session)
      self.lastFileName = path.basename(session)

  def goto(self, pageName: str):
    if callable(self.pageHandler):
      self.pageHandler(pageName, State())

  def updateData(self, newPage: BasePage, state: State):
    self.currentPage = newPage
    newPageIndex = next(
      (i for i, page in enumerate(self.pages) if isinstance(newPage, page)),
      None
    )
    for i in range(len(self.pages)):
      self.gotoMenu.entryconfigure(i, label=self.gotoLabels[i])
    if newPageIndex is not None:
      self.gotoMenu.entryconfigure(
        newPageIndex, label=self.gotoLabels[newPageIndex] + " (current)"
      )

    for i, page in enumerate(self.pages):
      sufficient = page.stateSufficient(state)
      self.gotoMenu.entryconfig(i, state="normal" if sufficient else "disabled")

    if newPage.disableSaveHotkey:
      self.unregistHotkeys()
    else:
      self.registerHotkeys()

  def readRecentSessions(self):
    if path.exists(recentSessionsFile):
      with open(recentSessionsFile, "r") as file:
        self.recentSessions = [
          session for session in (line.strip() for line in file.readlines())
          if len(session) > 0 and path.exists(session)
        ]
    else:
      self.recentSessions = []

  def writeRecentSessions(self):
    with open(recentSessionsFile, "w") as file:
      file.writelines(line + "\n" for line in self.recentSessions)

  def populateRecentSessionsMenu(self):
    self.recentMenu.delete(0, "end")
    if len(self.recentSessions) > 0:
      for session in self.recentSessions[:19]:
        label = (
          path.basename(session).replace(".imarr", "")
          if path.relpath(session).startswith("sessions") else session
        )
        self.recentMenu.add_command(
          label=label, command=partial(self.loadSession, session)
        )
    else:
      self.recentMenu.add_command(label="No recent sessions", state="disabled")

  def addRecentSession(self, session: str):
    try:
      self.recentSessions.remove(session)
    except ValueError:
      pass
    self.recentSessions.insert(0, session)
    self.populateRecentSessionsMenu()
    self.writeRecentSessions()
