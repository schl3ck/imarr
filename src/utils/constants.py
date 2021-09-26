from typing import Dict
import cdasws
from pathlib import Path
import tkinter as tk
from os import path
from dataclasses import dataclass

padding = 6
navigationButtonInnerPadding = 8
requestCheckInterval = 250    # ms
requestMaxRetries = 1
doubleClickTime = 500    # ms
minDragDistanceForDraggingInPlot = 10    # px, set to `0` to disable
cacheFolder = "./cache/"
cacheFolderNotFolder = False
try:
  # create cache folder
  Path(cacheFolder).mkdir(parents=True, exist_ok=True)
except FileExistsError:
  # "cache" is already existing and is a file
  cacheFolderNotFolder = True

cdas = cdasws.CdasWs(timeout=30)

# these are required
instrumentTypes = ["Magnetic Fields (space)"]    # "Plasma and Solar Wind"
requiredVariables = ["Magnetic Field"]

# these are optional
optionalVariables = [
  "Plasma Beta",
  "Plasma Pressure",
  "Particle Density",
  "Particle Speed",
  "Temperature"
]

@dataclass
class ImageCheckbox:
  empty: tk.PhotoImage = None
  checked: tk.PhotoImage = None
  modelInvalid: tk.PhotoImage = None

imageCheckbox = ImageCheckbox()

def initCheckboxImages():
  global imageCheckbox
  baseDir = path.join(path.dirname(__file__), "..", "assets")
  imageCheckbox.empty = tk.PhotoImage(
    file=path.join(baseDir, "checkbox-empty.png")
  )
  imageCheckbox.checked = tk.PhotoImage(
    file=path.join(baseDir, "checkbox-checked.png")
  )
  imageCheckbox.modelInvalid = tk.PhotoImage(
    file=path.join(baseDir, "model-invalid.png")
  )
