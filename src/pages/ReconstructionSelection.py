from dataclasses import dataclass
from functools import partial
import re
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, Dict, List, Type

from src.utils.importAllModels import importAllModels
from src.pages.BasePage import BasePage
from src.models.dummy import Model
from src.utils.ScrollableFrame import ScrollableFrame
from src.utils.utils import ensureOnScreen, scrollableTreeview
from src.utils.State import State
from src.utils.constants import padding, imageCheckbox


class ModelWithSelection:
  model: Type[Model] = None
  selected = False
  selectable = True
  treeviewId: str = None

  def __init__(self, model: Type[Model], state: State) -> None:
    self.model = model
    self.selectable = all(
      state.selectedVars.has(variable) for variable in model.requiredVariables
    )

  def __eq__(self, o: object) -> bool:
    if not isinstance(o, ModelWithSelection):
      return False
    return self.model.name == o.model.name


loadedModules: Dict[str, ModelWithSelection] = {}


class ReconstructionSelection(BasePage):
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

    master.title("Reconstruction Model Selection - IMARR")

    self.grid()

    self.createModelSelection()
    self.reloadModels()

    if state.models is not None:
      for model in state.models:
        module = loadedModules[model.name]
        if module and not module.selected:
          self.toggleModule(module)

    self.bBack = ttk.Button(
      self, text="Back", command=partial(self.goDirection, "back")
    )
    self.bBack.grid(column=1, row=2, padx=padding, pady=padding, sticky="we")
    self.bContinue = ttk.Button(
      self, text="Continue", command=partial(self.goDirection, "forward")
    )
    self.bContinue.grid(
      column=2, row=2, padx=padding, pady=padding, sticky="we"
    )

  def reloadModels(self, refresh=False):
    self.importModels(refresh)
    self.refreshModelSelectionList()
    if hasattr(self, "moduleDescriptionLabel"):
      self.moduleDescriptionLabel["text"] = ""

  def importModels(self, refresh=False):
    global loadedModules
    loaded = {
      model.name: ModelWithSelection(model, self.state)
      for model in importAllModels(refresh)
    }
    for (key, model) in loaded.items():
      if key in loadedModules:
        model.selected = (
          loadedModules[key].selected and loadedModules[key].selectable
        )
    loadedModules = loaded

  def createModelSelection(self):
    leftFrame = tk.Frame(self)
    leftFrame.grid(row=1, column=1)

    (
      self.modulesFrame,
      self.modulesTreeview,
      self.selectModelButton,
      self.reloadButton
    ) = (
      scrollableTreeview(
        leftFrame,
        "Please select at least one model to continue",
        ["Select Model", "Reload Models"],
        unpackButtons=True,
        noXScrollbar=True
      )
    )
    self.modulesFrame.grid(row=1, column=1, padx=padding)
    self.modulesTreeview["columns"] = tuple()
    self.modulesTreeview.column("#0", width=200, stretch=True)
    self.modulesTreeview.configure(show="tree", height=10)
    self.modulesTreeview.bind("<<TreeviewSelect>>", self.showDescription)
    self.modulesTreeview.bind("<Button-1>", self.showDescription)
    self.modulesTreeview.bind("<space>", self.toggleModule)

    self.selectModelButton["command"] = self.toggleModule
    self.reloadButton["command"] = partial(self.reloadModels, True)

    self.update_idletasks()

    self.rightFrame = ScrollableFrame(
      self,
      ttk.Frame,
      width=self.modulesFrame.winfo_width(),
      height=self.modulesFrame.winfo_height()
    )
    self.rightInnerFrame = self.rightFrame.innerFrame
    self.rightFrame.grid(column=2, row=1)

    self.moduleDescriptionLabel = ttk.Label(
      self.rightInnerFrame, wraplength=self.modulesFrame.winfo_width()
    )
    self.moduleDescriptionLabel.grid()
    ensureOnScreen(self.master)

  def refreshModelSelectionList(self):
    self.modulesTreeview.delete(*self.modulesTreeview.get_children())
    names = list(loadedModules.keys())
    names.sort()
    for name in names:
      # don't show the dummy model in the list
      if name == "Dummy Model":
        continue
      module = loadedModules[name]

      module.treeviewId = self.modulesTreeview.insert(
        "",
        tk.END,
        text=name,
        image=((
          imageCheckbox.checked if module.selected else imageCheckbox.empty
        ) if module.selectable else imageCheckbox.modelInvalid)
      )

  def showDescription(self, event: tk.Event):
    if event.char == " ":
      # space
      item = next(iter(self.modulesTreeview.selection()), None)
      toggle = True
    elif event.x and event.y:
      # click
      item = self.modulesTreeview.identify_row(event.y)
      toggle = 20 <= event.x <= 36
    else:
      # arrow keys
      item = next(iter(self.modulesTreeview.selection()), None)
      toggle = False

    if not item:
      self.moduleDescriptionLabel["text"] = ""
      return

    module = loadedModules[self.modulesTreeview.item(item, "text")]
    if toggle:
      self.toggleModule(module)
    else:
      if not module:
        return
      self.updateSelectButton(module)
      model = module.model
      firstLine = next(
        (line for line in model.__doc__.splitlines() if line.strip()), ""
      )
      lineIndent = 0
      for i in firstLine:
        if i != " " and i != "\t":
          break
        lineIndent += 1

      doc = "\n".join([
        line[lineIndent:] for line in model.__doc__.strip("\n\r").splitlines()
      ])
      doc = re.sub(r"([\w.,])\n(\w)", r"\1 \2", doc).strip()

      requiredVariables = ""
      if (not module.selectable or len(model.requiredVariables) > 1
          or model.requiredVariables[0] != "Magnetic Field"):
        l = model.requiredVariables
        if not module.selectable:
          l = [
            i + ("" if self.state.selectedVars.has(i) else " (missing)")
            for i in l
          ]
        requiredVariables = "\n\nRequired variables are:\n  * {}".format(
          "\n  * ".join(l)
        )
      self.moduleDescriptionLabel["text"] = doc + requiredVariables

  def toggleModule(self, module: ModelWithSelection = None):
    """
    Toggles the currently selected module
    """
    if not isinstance(module, ModelWithSelection):
      selection = self.modulesTreeview.selection()
      if len(selection) == 0:
        return
      name = self.modulesTreeview.item(selection[0], "text")
      module = loadedModules[name]

    if not module.selectable:
      return
    module.selected = not module.selected
    self.modulesTreeview.item(
      module.treeviewId,
      image=(imageCheckbox.checked if module.selected else imageCheckbox.empty)
    )
    self.updateSelectButton(module)

  def updateSelectButton(self, module: ModelWithSelection):
    self.selectModelButton["text"] = (
      "Deselct Model" if module.selected else "Select Model"
    )
    self.selectModelButton["state"] = (
      "normal" if module.selectable else "disabled"
    )

  def goDirection(self, direction: str):
    state = self.buildState()
    self.pageHandler(direction, state)

  def buildState(self):
    state = self.state.copy()
    state.models = [mws.model for mws in loadedModules.values() if mws.selected]
    return state

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
      "selectionEnd"
    ]
    return all(state.has(i) for i in needed)
