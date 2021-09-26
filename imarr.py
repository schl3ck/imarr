import tkinter as tk
from typing import List, Type
from astropy.time import Time

import sys
import logging

from src.pages.ObservatorySelection import ObservatorySelection
from src.pages.DatasetSelection import DatasetSelection
from src.pages.DownloadDataFiles import DownloadDataFiles
from src.pages.PlotSelection import PlotSelection
from src.pages.ReconstructionSelection import ReconstructionSelection
from src.pages.ReconstructionRunner import ReconstructionRunner, runningModels

from src.utils.constants import initCheckboxImages
from src.utils.State import State
from src.pages.BasePage import BasePage
from src.utils.getClassNameFromType import getClassNameFromType
from src.utils.MenuBar import MenuBar

logger = logging.getLogger("CdasWs")
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.DEBUG)

menuBar: MenuBar = None
activeWidgets: tk.Frame = None
state = State()
page = 0
initialPage = "ObservatorySelection"
pages: List[Type[BasePage]] = [
  ObservatorySelection,
  DatasetSelection,
  DownloadDataFiles,
  PlotSelection,
  ReconstructionSelection,
  ReconstructionRunner
]

# ============================
# page functions


def pageHandler(direction: str, result: State):
  global state, activeWidgets, page, pages

  if not state.includes(result):
    if not result.datasetCDFInstances or len(result.datasetCDFInstances) == 0:
      state.closeCDFFiles()
    state = result

  # print(state)

  if direction == "forward":
    page += 1
  elif direction == "back":
    page -= 1
  else:
    try:
      page = next(
        i for (i, page) in enumerate(pages)
        if getClassNameFromType(page) == direction
      )
    except StopIteration:
      return

  if page < 0:
    page = 0
  if page >= len(pages):
    page = len(pages) - 1

  nextPage = pages[page]
  if (direction == "back" and hasattr(nextPage, "skipOnBackward")
      and nextPage.skipOnBackward):
    page -= 1
    if page < 0:
      page = 0
    nextPage = pages[page]

  if activeWidgets:
    activeWidgets.destroy()

  activeWidgets = nextPage(root, pageHandler, state)
  menuBar.updateData(activeWidgets, state)


def onSessionLoad(session: State):
  global state
  state = session
  runningModels.clear()
  pageHandler("ObservatorySelection", state)


def onSessionSave():
  global state, activeWidgets
  if activeWidgets is not None:
    session = activeWidgets.buildState()
    return session if not state.includes(session) else state
  return None


# =============================================
# starting the app

root = tk.Tk()

initCheckboxImages()

root.minsize(300, 50)
root.resizable(False, False)
menuBar = MenuBar(root)
menuBar.onSessionLoad = onSessionLoad
menuBar.onSessionSave = onSessionSave
menuBar.pageHandler = pageHandler
root["menu"] = menuBar
pageHandler(initialPage, state)
root.iconbitmap(default="src/assets/icon.ico")
root.mainloop()

# cdaweb.sci.gsfc.nasa.gov/WS/cdasr/1/dataviews/sp_phys/observatories
