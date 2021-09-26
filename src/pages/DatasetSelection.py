import re
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from astropy.time import Time
from datetime import datetime
from typing import Dict, Union, Callable, Tuple
from functools import partial, reduce

from src.pages.BasePage import BasePage
from src.utils.cache import Cache
from src.utils.constants import (
  padding,
  cdas,
  instrumentTypes,
  requiredVariables,
  optionalVariables,
  navigationButtonInnerPadding,
  doubleClickTime,
  imageCheckbox
)
from src.utils.utils import (
  ensureOnScreen,
  scrollableTreeview,
  dictToGridLabels,
  languageJoin,
  pickFromDict,
  Time2StrCdasArgument
)
from src.utils.ScrollableFrame import ScrollableFrame
from src.utils.State import (
  State, StateSelectedVars, StateSelectedVar, StateDataset
)
from src.utils.ToolTip import ToolTip

treeViewHeights = {"dataset": 8, "variable": 8, "windowResized": False}

BfieldRegex = {
  "x": r"B[xX]|(^|[^\da-z])[xX]([^\da-z]|$)",
  "y": r"B[yY]|(^|[^\da-z])[yY]([^\da-z]|$)",
  "z": r"B[zZ]|(^|[^\da-z])[zZ]([^\da-z]|$)",
  "vector": r"B(field|[^\da-z]|$)",
  "total": r"B(tot|total)|(^|[^\da-z])(tot|total)([^\da-z]|$)"
}


class BFieldDirectionSelector:
  def __init__(
    self,
    parent: tk.Frame,
    state: State,
    onContinue: Callable[[bool, State], None]
  ):
    self.state = state
    self.onContinue = onContinue

    self.toplevel = tk.Toplevel(parent)
    # self.toplevel.transient(parent)
    self.toplevel.grab_set()
    self.toplevel.title("Magnetic Field Direction Selection - IMARR")
    self.toplevel.bind("<Escape>", self.onCancel)

    ttk.Label(
      self.toplevel,
      text="Please choose the direction of the magnetic field components"
    ).grid(
      row=0,
      column=0,
      columnspan=len(BfieldRegex.keys()) + 1,
      padx=padding,
      pady=padding
    )

    self.radioVariables = {
      key: tk.IntVar(self.toplevel, value=-1)
      for key in BfieldRegex.keys()
    }
    row = 1
    labels = []
    for i, var in enumerate(state.selectedVars.Magnetic_Field):
      label = ttk.Label(self.toplevel, text=var.variable, wraplength=250)
      label.tooltip = ToolTip(
        label, text="From dataset:\n" + var.dataset, wraplength=250
      )
      label.grid(row=row, column=0, padx=padding)
      labels.append(label)

      for i2, key in enumerate(BfieldRegex.keys()):
        radio = ttk.Radiobutton(
          self.toplevel, variable=self.radioVariables[key], value=i, text=key
        )
        radio["command"] = partial(self.onRadioClick, var, key, i)
        radio.grid(row=row, column=i2 + 1, padx=padding)
        if var.Bfield == key:
          radio.invoke()

      row += 1

    if all(var.get() < 0 for var in self.radioVariables.values()):
      for i, var in enumerate(state.selectedVars.Magnetic_Field):
        for key, regex in BfieldRegex.items():
          if re.search(regex, var.variable, re.IGNORECASE):
            self.radioVariables[key].set(i)
            self.onRadioClick(var, key, i)
            break

    self.buttonFrame = ttk.Frame(self.toplevel)
    self.buttonFrame.grid(
      row=row,
      column=0,
      columnspan=len(BfieldRegex.keys()) + 1,
      padx=padding,
      pady=padding,
      sticky="we"
    )

    self.cancelBtn = ttk.Button(
      self.buttonFrame, text="Cancel", command=self.onCancel
    )
    self.cancelBtn.pack(side="left", fill="x", expand=True)
    self.okBtn = ttk.Button(self.buttonFrame, text="OK", command=self.onOK)
    self.okBtn.pack(side="left", fill="x", expand=True)

    self.toplevel.update_idletasks()
    self.toplevel.geometry(
      "+{}+{}".format(
        parent.master.winfo_x()
        + int((parent.master.winfo_width() - self.toplevel.winfo_width()) / 2),
        parent.master.winfo_y()
        + int((parent.master.winfo_height() - self.toplevel.winfo_height()) / 2)
      )
    )
    self.toplevel.focus_set()

  def onRadioClick(self, var: StateSelectedVar, fieldDir: str, index: int):
    var.Bfield = fieldDir
    for key, radioVar in self.radioVariables.items():
      if key != fieldDir and radioVar.get() == index:
        radioVar.set(-1)
    for v in self.state.selectedVars.Magnetic_Field:
      if v != var and v.Bfield == fieldDir:
        v.Bfield = None

  def onOK(self):
    # TODO: check if a direction is missing
    self.toplevel.destroy()
    self.onContinue(self.state)

  def onCancel(self, event=None):
    self.toplevel.destroy()


class DatasetVariableSelection(tk.Frame):
  def __init__(
    self,
    master,
    title: str,
    variableChanged: Callable[[Tuple[str, str]], None],
    singleSelect: bool,
    state: State,
    **kwargs
  ):
    global treeViewHeights

    super().__init__(master, **kwargs)
    self.master = master
    self.variableChanged = variableChanged
    self.singleSelect = singleSelect
    self.title = title
    self.state = state

    self.tvFrame, self.treeView = scrollableTreeview(self, title=title)
    self.tvFrame.pack(side="top", padx=padding, pady=padding)

    self.treeView.configure(
      height=treeViewHeights["variable"], show="tree", selectmode="browse"
    )
    self.treeView.column("#0", width=210, stretch=True)
    self.treeView.bind("<Down>", self.onArrowKey)
    self.treeView.bind("<Up>", self.onArrowKey)
    self.treeView.bind("<<TreeviewSelect>>", self.variableSelected)
    self.treeView.bind("<space>", self.variableSelected)

    self.datasets = []
    self.treeViewItems = {}
    # look up variable & dataset by tree view items
    self.treeViewLookup = {}
    # look up tree view items by dataset & variable (key = tuple of str)
    self.treeViewReverseLookup = {}
    # the last time an arrow key was pressed
    self.arrowKeyPressed: datetime = None

  def onArrowKey(self, event):
    self.arrowKeyPressed = datetime.now()

  def variableSelected(self, event):
    selection = self.treeView.selection()
    if len(selection) == 0:
      return
    selection = selection[0]

    if (self.arrowKeyPressed and
        (datetime.now() - self.arrowKeyPressed).total_seconds() < 0.2
        and event.char != " "):
      # don't change when an arrow key was pressed but ignore it when space was
      # pressed
      return

    if selection not in self.treeViewLookup:
      return
    ownName = str(self)
    datasetVariable = self.treeViewLookup[selection]
    variable = datasetVariable["variable"]

    if self.singleSelect:
      for dataset in self.datasets:
        if ("variables" in dataset and isinstance(dataset["variables"], list)):
          for v in dataset["variables"]:
            # don't toggle for the current variable to be able to deselect it
            if v["selected"] == ownName and v["Name"] != variable["Name"]:
              v["selected"] = ""
              self.variableChanged((dataset["Id"], v["Name"]))
              self.updateVariable((dataset["Id"], v["Name"]))

    variable["selected"] = (ownName if variable["selected"] != ownName else "")
    self.treeView.item(
      selection,
      image=(
        imageCheckbox.checked
        if variable["selected"] == ownName else imageCheckbox.empty
      )
    )
    self.variableChanged((datasetVariable["dataset"]["Id"], variable["Name"]))

  def updateVariable(self, datasetAndVariable):
    item = self.treeViewReverseLookup[datasetAndVariable]
    variable = self.treeViewLookup[item]["variable"]
    self.treeView.item(
      item,
      image=(
        imageCheckbox.checked
        if variable["selected"] == str(self) else imageCheckbox.empty
      )
    )

  def setDatasets(self, datasets):
    newItems = [
      dataset for dataset in enumerate(datasets)
      if dataset[1] not in self.datasets
    ]
    removeItems = [
      dataset for dataset in self.datasets if dataset not in datasets
    ]
    self.datasets = datasets

    for item in removeItems:
      tvId = self.treeViewItems[item["Id"]]
      for child in self.treeView.get_children(tvId):
        self.treeViewLookup.pop(child, None)
      self.treeView.delete(tvId)
      self.treeViewItems.pop(item["Id"], None)

    for i, item in newItems:
      self.treeViewItems[item["Id"]] = self.treeView.insert(
        "", i, text=item["Label"]
      )

    self.updateVariables()

    items = list(self.treeViewItems.values())
    if len(items) > 0:
      if len(items) == 1:
        self.treeView.item(items[0], open=True)
      else:
        for item in items:
          self.treeView.item(item, open=False)

  def updateVariables(self):
    for dataset in self.datasets:
      item = self.treeViewItems[dataset["Id"]]
      self.treeView.delete(*self.treeView.get_children(item))
      if ("variables" in dataset and isinstance(dataset["variables"], list)
          and len(dataset["variables"])):
        for variable in dataset["variables"]:
          varItem = self.treeView.insert(
            item,
            tk.END,
            text=variable["Name"],
            image=(
              imageCheckbox.checked
              if variable["selected"] == str(self) else imageCheckbox.empty
            )
          )
          self.treeViewLookup[varItem] = {
            "variable": variable,
            "dataset": dataset,
          }
          self.treeViewReverseLookup[(dataset["Id"], variable["Name"])
                                     ] = varItem

  def getVariables(self):
    ownName = str(self)
    variables = []
    varName = self.title.replace(" (required)", "")
    for dataset in self.datasets:
      if ("variables" in dataset and isinstance(dataset["variables"], list)):
        for v in dataset["variables"]:
          if v["selected"] == ownName:
            ssv = StateSelectedVar(dataset["Id"], v["Name"])
            known = (
              next((
                i for i in self.state.selectedVars[varName]
                if i.representsSameVariable(ssv)
              ),
                   None) if isinstance(self.state.selectedVars, list) else None
            )
            if known is not None and known != ssv:
              ssv = known
            variables.append(ssv)
    return variables


class DatasetSelection(BasePage):
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
    self.cache = Cache(
      "datasets_{}_{}_{}".format(
        state.observatory, state.startDate.value, state.endDate.value
      ),
      True
    )

    self.master.title("Dataset selection - IMARR")

    self.datasets = None
    self.lastSelectedDataset = None
    self.variableSelects: Dict[str, DatasetVariableSelection] = {}

    self.createStatusLabel()
    self.pack()
    self.bind("<Visibility>", self.loaded)

  def loaded(self, event):
    """
    Called, once the window is shown. Flushes any queued drawing and
    loads the datasets.
    """
    self.update_idletasks()
    self.getDataset()

  def createStatusLabel(self):
    self.lbStatus = ttk.Label(self, text="", justify="left")
    self.lbStatus.grid(
      column=1, row=1, padx=padding * 3, pady=padding * 3, sticky="w"
    )

  def getDataset(self):
    """
    Load the datasets for the selected observatory and dates
    """
    self.lbStatus["text"] = "Retrieving datasets"

    def load():
      options = {
        "observatory": self.state.observatory,
        "startDate": Time2StrCdasArgument(self.state.startDate),
        "endDate": Time2StrCdasArgument(self.state.endDate)
      }
      return cdas.get_datasets(**options)

    def done(fromCache, value, err=None):
      if err is not None:
        print(err)
        return
      start = self.state.startDate
      end = self.state.endDate
      filtered = []
      for ds in value:
        if (Time(ds["TimeInterval"]["Start"], format="isot") > end
            or Time(ds["TimeInterval"]["End"], format="isot") < start):
          continue
        ds["Label"] = ds["Label"].replace("\t", " ")
        filtered.append(ds)
      filtered.sort(key=lambda item: str.lower(item["Label"]))
      self.datasets = filtered
      if fromCache:
        self.checkDatasetsLoaded()
      else:
        self.after(1, self.checkDatasetsLoaded())

    self.cache.get(
      load,
      done,
      onError=lambda err: done(False, False, err),
    )

  def checkDatasetsLoaded(self):
    """Checks if the loading of the datasets has finished
    """
    if self.datasets is False or (isinstance(self.datasets, list)
                                  and len(self.datasets) == 0):
      # error while loading
      self.lbStatus["text"] = (
        "There was an error while loading the datasets"
        if self.datasets is False else
        "No datasets that contain data in the selcted time period were found"
      )
      self.lbStatus["foreground"] = "red"
      self.lbStatus.grid(
        column=1, row=1, padx=padding * 3, pady=padding * 3, sticky="w"
      )
      self.btnBack = ttk.Button(self, text="Back", command=self.back)
      self.btnBack.pack(side="top", fill="x", padx=padding, pady=padding)
    else:
      # loaded
      self.lbStatus.grid_forget()
      for dataset in self.datasets:
        dataset["selected"] = False
        dataset["cache"] = Cache(
          "dataset_variables_{}".format(dataset["Id"]), True
        )
      self.showDatasets()

  def showDatasets(self):
    """Creates all widgets and inserts all datasets in the tree view
    """
    global treeViewHeights
    row = 2

    # dataset treeview
    (self.frameDatasets, self.tvDatasets,
     self.bSelectDataset) = scrollableTreeview(
       self,
       title=
       "Please select the datasets so that they contain the instrument types "
       + languageJoin(instrumentTypes, quoteItems="\"")
       + " (click on checkbox or press space)",
       button="Select Dataset"
     )
    self.tvDatasets.bind("<<TreeviewSelect>>", self.datasetSelected)
    self.tvDatasets.bind("<Button-1>", self.datasetSelected)
    self.tvDatasets.bind("<space>", self.datasetSelected)
    self.tvDatasets["selectmode"] = tk.BROWSE

    self.tvDatasets["columns"] = ("#1", "#2", "#3")
    self.tvDatasets.column("#0", width=350, stretch=True)
    self.tvDatasets.column("#1", width=100, stretch=True)
    self.tvDatasets.column("#2", width=170, stretch=True)
    self.tvDatasets.column("#3", width=170, stretch=True)
    self.tvDatasets.heading("#0", text="Label")
    self.tvDatasets.heading("#1", text="Instrument")
    self.tvDatasets.heading("#2", text="Start")
    self.tvDatasets.heading("#3", text="End")

    self.tvDatasets["height"] = treeViewHeights["dataset"]

    hasDatasets = bool(self.state.datasets)
    datasetIds = ([d.id for d in self.state.datasets] if hasDatasets else [])
    for dataset in self.datasets:
      if dataset["Id"] in datasetIds:
        dataset["selected"] = True
      item = self.tvDatasets.insert(
        "",
        tk.END,
        text=dataset["Label"],
        values=[
          dataset["Instrument"],
          dataset["TimeInterval"]["Start"],
          dataset["TimeInterval"]["End"]
        ],
        image=(
          imageCheckbox.checked if dataset["selected"] else imageCheckbox.empty
        )
      )
      dataset["tvItem"] = item

    self.bSelectDataset["command"] = self.selectDataset
    self.bSelectDataset["state"] = tk.DISABLED

    self.frameDatasets.grid(column=1, row=row, padx=padding, pady=padding)
    self.master.update()

    # selected dataset details

    width = 600
    frame = tk.Frame(self)
    frame.grid(column=2, row=row, padx=padding, pady=padding, sticky="nsew")

    # padder = tk.Label(frame, text="")
    # padder.pack(side="top", padx=padding, pady=0)

    # scrollable frame
    scrollFrame = ScrollableFrame(
      frame,
      ttk.Frame,
      width=width,
      height=self.frameDatasets.winfo_height()
    )
    self.fDescription = scrollFrame.innerFrame
    scrollFrame.pack(side="top")
    self.cDescription = scrollFrame.canvas

    # get variables button

    row += 1
    self.bGetVariables = ttk.Button(
      self, text="Get Variables", state=tk.DISABLED, command=self.getVariables
    )
    self.bGetVariables.grid(
      column=1, row=row, columnspan=2, sticky="we", padx=padding, pady=padding
    )

    # variable selection

    row += 1
    self.lbVariableSelection = tk.Label(
      self,
      text="Please select the variables you need from the selected datasets."
    )
    self.lbVariableSelection.grid(column=1, row=row, columnspan=2)

    row += 1
    self.fVaraibleSelections = tk.Frame(self)
    self.fVaraibleSelections.grid(column=1, row=row, columnspan=2, sticky="we")

    def addVarSelection(title):
      widget = DatasetVariableSelection(
        self.fVaraibleSelections,
        title,
        self.variableChanged,
      # singleSelect:
        "Magnetic Field" not in title,
        self.state
      )
      widget.pack(side="left")
      return widget

    for var in requiredVariables:
      self.variableSelects[var] = addVarSelection(var + " (required)")
    for var in optionalVariables:
      self.variableSelects[var] = addVarSelection(var)

    # navigation buttons

    row += 1
    frameBtns = tk.Frame(self)
    self.btnBack = ttk.Button(frameBtns, text="Back", command=self.back)
    self.btnContinue = ttk.Button(frameBtns, text="Continue", command=self.done)
    self.btnBack.pack(
      side="left",
      padx=padding,
      pady=padding,
      expand=True,
      fill="x",
      ipady=navigationButtonInnerPadding
    )
    self.btnContinue.pack(
      side="left",
      padx=padding,
      pady=padding,
      expand=True,
      fill="x",
      ipady=navigationButtonInnerPadding
    )
    frameBtns.grid(column=1, row=row, columnspan=2, pady=padding, sticky="we")

    if not treeViewHeights["windowResized"]:
      # resize window if it is too small
      self.update_idletasks()
      initialHeight = self.master.winfo_height()
      maxHeight = min(self.master.winfo_screenheight() - 150, 900)

      def setTvVariableHeight():
        for widget in self.variableSelects.values():
          widget.treeView["height"] = treeViewHeights["variable"]

      def setTvDatasetHeight():
        self.tvDatasets["height"] = treeViewHeights["dataset"]
        self.update_idletasks()
        self.cDescription["height"] = self.frameDatasets.winfo_height()

      treeViewHeights["variable"] += 1
      setTvVariableHeight()
      self.update_idletasks()
      updatedHeight = self.master.winfo_height()
      lineHeight = updatedHeight - initialHeight
      linesToAdd = (maxHeight - updatedHeight) // lineHeight
      if linesToAdd > 0:
        treeViewHeights["dataset"] += round(linesToAdd / 3 * 2)
        treeViewHeights["variable"] += round(linesToAdd / 3)
        setTvVariableHeight()
        setTvDatasetHeight()
        self.update_idletasks()
      treeViewHeights["windowResized"] = True

    self.updateTvVariables(True)
    ensureOnScreen(self.master)

  def datasetSelected(self, event: tk.Event):
    """
    Called when a dataset is selected in the tree view. A double click
    toggles the selected state
    """
    def clearChildren():
      children = list(self.fDescription.children.values())
      for c in children:
        c.destroy()

    if event.char == " ":
      # space
      item = next(iter(self.tvDatasets.selection()), None)
      toggle = True
    elif event.x and event.y:
      # click
      item = self.tvDatasets.identify_row(event.y)
      toggle = 20 <= event.x <= 36
    else:
      # arrow keys
      item = next(iter(self.tvDatasets.selection()), None)
      toggle = False

    if not item:
      clearChildren()
      return
    index = self.tvDatasets.index(item)
    dataset = self.datasets[index]

    if toggle:
      self.selectDataset(dataset)
    else:
      if item != self.lastSelectedDataset:
        # only rebuild the info when the dataset has changed after some time
        # to not block the double click
        self.lastSelectedDataset = item
        clearChildren()

        keys = [
          "Id",
          "Label",
          "ObservatoryGroup",
          "Observatory",
          "InstrumentType",
          "Instrument",
          "TimeInterval",
          "PiName",
          "PiAffiliation",
          "Notes",
          "DatasetLink"
        ]
        dictToGridLabels(self.fDescription, dataset, keys, 500)

        self.master.update()
        self.cDescription["width"] = self.fDescription.winfo_width()

      self.bSelectDataset["state"] = tk.NORMAL
      self.bSelectDataset["text"] = (
        "Deselct Dataset" if dataset["selected"] else "Select Dataset"
      )

  def selectDataset(self, dataset=None):
    """
    Toggles the currently selected dataset
    """
    if dataset is None:
      selection = self.tvDatasets.selection()
      if len(selection) == 0:
        return
      index = self.tvDatasets.index(selection[0])
      dataset = self.datasets[index]
    dataset["selected"] = not dataset["selected"]
    self.tvDatasets.item(
      dataset["tvItem"],
      image=(
        imageCheckbox.checked if dataset["selected"] else imageCheckbox.empty
      )
    )
    self.bSelectDataset["text"] = (
      "Deselct Dataset" if dataset["selected"] else "Select Dataset"
    )
    self.updateTvVariables(False)

  def updateTvVariables(self, checkSelectedVariables):
    """
    Updates the variable selection tree views based on the selected datasets
    """
    selected = [dataset for dataset in self.datasets if dataset["selected"]]
    for widget in self.variableSelects.values():
      widget.setDatasets(selected)
    self.bGetVariables["state"] = (
      tk.NORMAL if len(selected) > 0 else tk.DISABLED
    )

    if (checkSelectedVariables):
      hasSelection = (
        isinstance(self.state.selectedVars, StateSelectedVars) and
        reduce((lambda a, b: a + len(b)), self.state.selectedVars.values(),
               0) > 0
      )
      if (hasSelection):
        self.getVariables(True)

  def getVariables(self, checkSelectedVariables=False):
    """
    Load the variables of all selected datasets
    """
    self.datasetsLoaded = {}
    self.bGetVariables.configure(
      state=tk.DISABLED, text="Retrieving Variables..."
    )
    for dataset in self.datasets:
      if not dataset["selected"]:
        continue

      self.datasetsLoaded[dataset["Id"]] = False

      dataset["cache"].get(
        partial(self.loadVariable, dataset),
        partial(self.variableLoaded, dataset, checkSelectedVariables),
        onError=partial(self.variableLoaded, dataset, True, False, None)
      )

  def loadVariable(self, dataset):
    """
    Load the variables of one dataset. Used in self.getVariables
    """
    return cdas.get_variables(dataset["Id"])

  def variableLoaded(self, dataset, checkSelectedVariables, fromCache, value):
    """
    Called from Cache when the variables have been loaded and updates all
    variable-widgets once all datasets have been loaded.
    Used in self.getVariables
    """
    if fromCache and not value:
      self.lbStatus["text"] = """There was a problem loading the variables.
Please check your internet connection and try again or restart the program.
If this error persits, please check for a new version or contact the developer."""
      self.lbStatus["foreground"] = "red"
      self.lbStatus.grid(
        column=1, row=1, padx=padding * 3, pady=padding, sticky="w"
      )
      self.bGetVariables["text"] = "Get Variables"
      self.bGetVariables["state"] = tk.NORMAL
      return

    for var in value:
      if checkSelectedVariables:
        varName = self.state.selectedVars.find(dataset["Id"], var["Name"])
        var["selected"] = (
          str(self.variableSelects[varName.key])
          if varName is not None else False
        )
      else:
        var["selected"] = False
    value.sort(key=lambda item: str.lower(item["Name"]))
    dataset["variables"] = value
    self.datasetsLoaded[dataset["Id"]] = True

    if all(self.datasetsLoaded.values()):
      self.bGetVariables.configure(state=tk.NORMAL, text="Get Variables")
      for widget in self.variableSelects.values():
        if fromCache:
          widget.updateVariables()
        else:
          widget.after(1, widget.updateVariables)

      errors = [
        dataset["Label"]
        for dataset in self.datasets
        if "variables" in dataset and dataset["variables"] is False
      ]
      if len(errors) > 0:
        messagebox.showerror(
          title="Failed to load variables",
          message="Failed to load the variables for the datasets:\n\n\t"
          + "\n\t".join(errors)
          + "\n\nPlease check your internet connection and try again."
        )

  def variableChanged(self, datasetAndVariable):
    for widget in self.variableSelects.values():
      widget.updateVariable(datasetAndVariable)

  def goDirection(self, direction: str):
    res = self.buildState()

    if (res.selectedVars.Magnetic_Field is not None
        and len(res.selectedVars.Magnetic_Field) > 1
        and direction == "forward"):
      BFieldDirectionSelector(self, res, self.BfieldCallback)
    else:
      self.pageHandler(direction, res)

  def BfieldCallback(self, state: State):
    self.pageHandler("forward", state)

  def back(self):
    """
    Called when the user wants to go one page back
    """
    self.goDirection("back")

  def done(self):
    """
    Called when the user clicks the "Continue" button to go to the next step
    """
    selectedVars = {
      var: self.variableSelects[var].getVariables()
      for variables in [requiredVariables, optionalVariables]
      for var in variables
    }
    missingVariables = [
      var for var in requiredVariables if len(selectedVars[var]) == 0
    ]

    if len(missingVariables) > 0:
      messagebox.showerror(
        title="Missing variable" + ("s" if len(missingVariables) > 1 else ""),
        message="The following variables are missing:\n\n"
        + "\n".join(missingVariables)
        + "\n\nPlease select the missing variables to proceed."
      )
      return

    self.goDirection("forward")

  def buildState(self):
    selectedVars = ((var, self.variableSelects[var].getVariables())
                    for variables in [requiredVariables, optionalVariables]
                    for var in variables)

    res = State()
    res.observatory = self.state.observatory
    res.startDate = self.state.startDate
    res.endDate = self.state.endDate
    res.datasets = [
      StateDataset(dataset["Id"], dataset["Label"])
      for dataset in self.datasets
      if dataset["selected"]
    ]
    res.selectedVars = StateSelectedVars({
      var: val
      for (var, val) in selectedVars
      if len(val) > 0
    })
    return res

  @staticmethod
  def stateSufficient(state: State):
    needed = ["observatory", "startDate", "endDate"]
    return all(state.has(i) for i in needed)
