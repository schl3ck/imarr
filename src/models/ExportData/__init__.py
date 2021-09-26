from datetime import datetime
from gzip import compress
from src.utils.utils import openLink, setFillValuesToNan
from time import sleep
from typing import Any, Callable, Dict, List, Set, Union
from tkinter import Frame, Toplevel
from cdflib.cdfread import CDF as CDFRead
from cdflib.cdfwrite import CDF
from cdflib import cdfastropy, cdfepoch
from astropy.time import Time, TimeDelta
import tkinter as tk
import tkinter.ttk as ttk
from tkinter.messagebox import showwarning
from tkinter.filedialog import asksaveasfilename
from dataclasses import dataclass
import numpy as np
import re
from functools import partial

from src.utils.State import State
from src.utils.constants import padding

varnames = [
  "magField",
  "magFieldTotal",
  "beta",
  "pressure",
  "density",
  "speed",
  "temperature"
]
selectedVarNameLookup = {
  "magField": "Magnetic Field",
  "magFieldTotal": "Magnetic Field",
  "beta": "Plasma Beta",
  "pressure": "Plasma Pressure",
  "density": "Particle Density",
  "speed": "Particle Speed",
  "temperature": "Temperature"
}


@dataclass
class VarNames:
  magField: str = "magField"
  magFieldTotal: str = "magFieldTotal"
  beta: str = "beta"
  pressure: str = "pressure"
  density: str = "density"
  speed: str = "speed"
  temperature: str = "temperature"


@dataclass
class Settings:
  # name of vars to export
  exportVars: Set[str]
  varNames: VarNames
  # all | selected | more
  rangeVariable: str = "selected"
  additionalPoints: int = 0
  exportMagAsVector: bool = False
  # cdf | text
  fileFormat: str = "cdf"
  compress: bool = False
  compressionLevel: int = 0
  fieldDelimiter: str = " "


class Model:
  """
  Export Data
  ===========

  This is not a reconstruction model but exports the selected data. Check the
  settings of this model before starting!
  """

  # this tells the application which variables are required so that it can
  # disable the model when some variables are missing
  # for a list of variables have a look at `src/utils/constants.py`
  # "requiredVariables" and "optionalVariables"
  requiredVariables = ["Magnetic Field"]

  # the name of this model
  name = "Export Data"

  # set to True when this reconstruction has some options to configure
  hasSettings = True

  # set to True when this reconstruction can show some results
  hasResults = False

  def __init__(self):
    self.canceled = False

  def initSettings(self, state: State):
    self.settings = Settings(
      set(
        i for i in varnames if state.selectedVars.has(selectedVarNameLookup[i])
      ),
      VarNames()
    )

  def canRun(self) -> Union[bool, str]:
    """
    If the reconstruction model depends on certain packages, check for them
    here if they are installed. Return True only when the model can be run,
    otherwise return a string that describes the problem
    """
    return "Needs some coffee"

  def showSettings(self, window: Toplevel, state: State):
    """Called when the user wants to change some options"""
    window.title(f"Settings - {self.name} - IMARR")
    window.resizable(False, False)
    window.bind("<Destroy>", self.onSettingsClose)

    if getattr(self, "settings", None) is None:
      self.initSettings(state)

    self.settingsState = state
    variable = state.selectedVars.Magnetic_Field[0]
    cdf = state.datasetCDFInstances[variable.dataset]
    cdfInfo = cdf.cdf_info()
    depend0 = next((
      i["DEPEND_0"]
      for i in (cdf.varattsget(i) for i in cdfInfo["zVariables"])
      if "DEPEND_0" in i and i["DEPEND_0"] is not None
    ),
                   None)
    xData = cdfastropy.convert_to_astropy(cdf.varget(depend0 or "epoch"))
    xData.format = "iso"
    xData.precision = 3
    self.settingsDataStart = start = xData[0]
    self.settingsDataEnd = end = xData[-1]
    self.intervalSecs = round((xData[1] - xData[0]).sec, 3)
    intervalStr = self.secondsToMultiUnit(self.intervalSecs)
    maxAdditionalRange = int(
      min((state.selectionStart - start).sec / self.intervalSecs,
          (end - state.selectionEnd).sec / self.intervalSecs)
    )

    # range selection ==========================================================

    frame = ttk.Frame(window)
    frame.grid(column=1, row=1, padx=padding, pady=padding, sticky="wn")
    lb = ttk.Label(frame, text="Export ...")
    lb.grid(column=1, row=1, sticky="w")

    self.tkRangeVar = tk.StringVar(window, value=self.settings.rangeVariable)
    self.tkRangeVar.trace_add("write", self.settingsRangeVarChanged)

    rb = ttk.Radiobutton(
      frame, text="all data", variable=self.tkRangeVar, value="all"
    )
    rb.grid(column=1, row=2, sticky="w")
    rb = ttk.Radiobutton(
      frame, text="selected data", variable=self.tkRangeVar, value="selected"
    )
    rb.grid(column=1, row=3, sticky="w")
    rb = ttk.Radiobutton(
      frame,
      text="selected data + additional data at boundaries for smoothing",
      variable=self.tkRangeVar,
      value="more"
    )
    rb.grid(column=1, row=4, sticky="w")

    frame2 = ttk.Frame(frame)
    frame2.grid(column=1, row=5, padx=padding, sticky="w")
    lb = ttk.Label(frame2, text="Include")
    lb.grid(column=1, row=1, padx=padding, sticky="w")
    validator = (
      window.register(self.settingsAdditionalRangeValidator), "%V", "%P"
    )
    self.additionalPointsSpinbox = ttk.Spinbox(
      frame2,
      to=maxAdditionalRange,
      increment=1,
      validatecommand=validator,
      validate="all",
      command=self.settingsAdditionalRangeValidator,
      width=10
    )
    self.additionalPointsSpinbox["from"] = 0
    self.additionalPointsSpinbox.grid(column=2, row=1, sticky="w")
    self.additionalPointsSpinbox.set(self.settings.additionalPoints)
    lb = ttk.Label(frame2, text="additional data points on each side")
    lb.grid(column=3, row=1, padx=padding, sticky="w")
    self.additionalPointsLabel = ttk.Label(frame2, text="")
    self.additionalPointsLabel.grid(column=2, row=2, columnspan=2, sticky="w")

    frame = ttk.Frame(window)
    frame.grid(column=2, row=1, pady=padding, sticky="w")
    lb = ttk.Label(
      frame,
      text="""Data availability and selection:
Beginning of data:
Selection start:
Selection end:
End of data:
Time interval of data:"""
    )
    lb.grid(column=1, row=1, padx=padding, sticky="w")
    lb = ttk.Label(
      frame,
      text="\n"
      f"{start.value}\n"
      f"{state.selectionStart.value}\n"
      f"{state.selectionEnd.value}\n"
      f"{end.value}\n"
      f"{intervalStr}"
    )
    lb.grid(column=2, row=1, padx=padding, sticky="w")

    # update spinbox state
    self.settingsRangeVarChanged(None, None, None)
    self.settingsAdditionalRangeValidator("focus")

    # field names ==============================================================
    sep = ttk.Separator(window, orient="horizontal")
    sep.grid(
      column=1, row=2, columnspan=2, padx=padding, pady=padding, sticky="we"
    )
    frame = ttk.Frame(window)
    frame.grid(column=1, row=3, columnspan=2, padx=padding, sticky="we")
    lb = ttk.Label(frame, text="Export ...")
    lb.grid(column=1, row=0, sticky="w")

    self.settingsExportEnabledTkVariables: Dict[str, tk.IntVar] = {}
    self.settingsExportNameTkVariables: Dict[str, tk.StringVar] = {}

    for i, name in enumerate(["magField",
                 "magFieldTotal",
                 "beta",
                 "pressure",
                 "density",
                 "speed",
                 "temperature"]):
      row = i + 1
      selectedVar = state.selectedVars[selectedVarNameLookup[name]]
      selectedVarAvailable = selectedVar is not None and len(selectedVar) > 0
      if name == "magField":
        accept = ["x", "y", "z", "vector"]
        selectedVarAvailable = (
          selectedVarAvailable and any(i.Bfield in accept for i in selectedVar)
        )
      elif name == "magFieldTotal":
        selectedVarAvailable = (
          selectedVarAvailable
          and any(i.Bfield == "total" for i in selectedVar)
        )
      var = tk.IntVar(
        window,
        1 if selectedVarAvailable and name in self.settings.exportVars else 0
      )
      self.settingsExportEnabledTkVariables[name] = var
      var.trace_add("write", partial(self.settingsVarCheckbuttonChanged, name))
      cb = ttk.Checkbutton(
        frame,
        text=(("Total " if name == "magFieldTotal" else "")
              + selectedVarNameLookup[name]),
        variable=var,
        onvalue=1,
        offvalue=0,
        state="normal" if selectedVarAvailable else "disabled"
      )
      cb.grid(column=1, row=row, sticky="w")
      lb = ttk.Label(
        frame,
        text="as",
        state="normal" if selectedVarAvailable else "disabled"
      )
      lb.grid(column=2, row=row, padx=padding, sticky="w")
      entryVar = tk.StringVar(window, getattr(self.settings.varNames, name))
      entryVar.trace_add("write", partial(self.settingsExportNameChanged, name))
      self.settingsExportNameTkVariables[name] = entryVar
      entry = ttk.Entry(
        frame,
        textvariable=entryVar,
        state="normal" if selectedVarAvailable else "disabled"
      )
      entry.grid(column=3, row=row, pady=padding // 2, sticky="w")

      if name == "magField":
        var = tk.IntVar(
          window,
          1 if selectedVarAvailable and self.settings.exportMagAsVector else 0
        )
        self.settingsExportMagAsVektorTkVariable = var
        var.trace_add("write", self.settingsExportMagAsVectorChanged)
        cb = ttk.Checkbutton(
          frame,
          text=
          "as vector (contains all axes for each datapoint)\notherwise \"X\", \"Y\" and \"Z\" is appended (e.g. \"magFieldX\")\nonly for CDF files",
          variable=var,
          onvalue=1,
          offvalue=0
        )
        cb.grid(column=4, row=row, padx=padding, sticky="w")
      elif not selectedVarAvailable:
        lb = ttk.Label(frame, text="(contains no data)", state="disabled")
        lb.grid(column=4, row=row, padx=padding, sticky="w")

    # file type ================================================================
    sep = ttk.Separator(window, orient="horizontal")
    sep.grid(
      column=1, row=4, columnspan=2, padx=padding, pady=padding, sticky="we"
    )
    frame = ttk.Frame(window)
    frame.grid(column=1, row=5, columnspan=2, padx=padding, sticky="w")

    frame2 = ttk.Frame(frame)
    frame2.grid(column=1, row=1, columnspan=4, sticky="w")
    lb = ttk.Label(frame2, text="File format:")
    lb.grid(column=1, row=1, sticky="w")
    var = tk.StringVar(window, self.settings.fileFormat)
    self.settingsFileFormatTkVariable = var
    var.trace_add("write", self.settingsFileFormatChanged)
    rb = ttk.Radiobutton(frame2, text="CDF", value="cdf", variable=var)
    rb.grid(column=2, row=1, padx=padding, sticky="w")
    frame3 = ttk.Frame(frame2)
    frame3.grid(column=3, row=1, padx=padding, sticky="w")
    rb = ttk.Radiobutton(
      frame3, text="Text (using ", value="text", variable=var
    )
    rb.grid(column=1, row=1, sticky="w")
    lb = tk.Message(
      frame3, text="numpy.savetxt", fg="blue", cursor="hand2", width=500
    )
    lb.bind(
      "<Button-1>",
      lambda e: openLink(
        url=
        "https://numpy.org/doc/stable/reference/generated/numpy.savetxt.html"
      )
    )
    lb.grid(column=2, row=1, sticky="w")
    lb = ttk.Label(frame3, text=")")
    lb.bind("<Button-1>", lambda e: var.set("text"))
    lb.grid(column=3, row=1, sticky="w")

    var = tk.IntVar(window, 1 if self.settings.compress else 0)
    self.settingsCompressTkVariable = var
    var.trace_add("write", self.settingsCompressChanged)
    cb = ttk.Checkbutton(frame, text="Compress", variable=var)
    cb.grid(column=1, row=2, pady=padding / 2, sticky="w")

    lb = ttk.Label(frame, text="Compression level (only CDF files)")
    lb.grid(column=1, row=3, pady=padding / 2, sticky="w")
    var = tk.StringVar(window, str(self.settings.compressionLevel))
    self.settingsCompressionLevelTkVariable = var
    var.trace_add("write", self.settingsCompressionLevelChanged)
    cb = ttk.Combobox(
      frame,
      textvariable=var,
      state="readonly",
      values=list(range(10)),
      width=7
    )
    cb.grid(column=2, row=3, pady=padding / 2, sticky="w")
    self.settingsCompressionLevelWidget = cb

    lb = ttk.Label(frame, text="Field delimiter in text file")
    lb.grid(column=1, row=5, sticky="w")
    validator = (
      window.register(self.settingsValidateFieldDelimiter), "%V", "%P"
    )
    var = tk.StringVar(window, self.settings.fieldDelimiter)
    entry = ttk.Entry(
      frame,
      validate="all",
      validatecommand=validator,
      width=10,
      textvariable=var
    )
    entry.grid(column=2, row=5, pady=padding / 2, sticky="w")
    self.settingsFieldDelimiterEntryWidget = entry
    lb = ttk.Label(frame, text="")
    lb.grid(column=3, row=5, padx=padding, sticky="w")
    self.settingsFieldDelimiterDisplayWidget = lb
    def onBtn():
      var.set("\t")
      self.settingsValidateFieldDelimiter("focus", "\t")
    btn = ttk.Button(
      frame,
      text="Set to tab character",
      command=onBtn
    )
    btn.grid(column=4, row=5, sticky="w")
    self.settingsFieldDelimiterTabButton = btn
    # set state of fields
    self.settingsFileFormatChanged(None, None, None)
    self.settingsValidateFieldDelimiter("focus", self.settings.fieldDelimiter)

    btn = ttk.Button(window, text="OK", command=lambda: window.destroy())
    btn.grid(
      column=1, row=10, columnspan=2, padx=padding, pady=padding, sticky="we"
    )

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
    statusCallback(None, "Exporting...")

    if getattr(self, "settings", None) is None:
      self.initSettings(state)

    if not self.checkAllVariablesHaveName():
      errorCallback(
        "Some variables have an empty name assigned. Please assign them a name in the settings"
      )
      return

    cdfFileType = ("CDF File", "*.cdf")
    textFileType = ("Text File", "*.txt")
    compressedTextFileType = ("Compressed Text File", "*.txt.gz")

    fileType = ""
    if self.settings.fileFormat == "cdf":
      fileType = cdfFileType
    elif self.settings.compress:
      fileType = compressedTextFileType
    else:
      fileType = textFileType

    path = asksaveasfilename(
      confirmoverwrite=True,
      initialdir=".",
      title="Export Data to",
      filetypes=(fileType, ("All files", "*")),
      defaultextension=fileType[1].replace("*", "")
    )
    if len(path) == 0:
      errorCallback("Canceled by user")
      return

    epochs: Set[datetime] = set()
    epochatts: dict = None
    datasets = set(
      var.dataset
      for i in self.settings.exportVars
      for var in state.selectedVars[selectedVarNameLookup[i]]
    )
    for dataset in datasets:
      cdf = state.datasetCDFInstances[dataset]
      cdfInfo = cdf.cdf_info()
      depend0 = next((
        i["DEPEND_0"]
        for i in (cdf.varattsget(i) for i in cdfInfo["zVariables"])
        if "DEPEND_0" in i and i["DEPEND_0"] is not None
      ),
                     None)
      atts = cdf.varattsget(depend0 or "epoch", expand=True)
      epoch = cdfastropy.convert_to_astropy(cdf.varget(depend0 or "epoch"))
      epoch.format = "datetime"

      if self.settings.rangeVariable == "all":
        pass
      elif self.settings.rangeVariable == "selected":
        epoch = epoch[epoch >= state.selectionStart]
        epoch = epoch[epoch <= state.selectionEnd]
      elif self.settings.rangeVariable == "more":
        i1 = np.nonzero(epoch.value >= state.selectionStart.datetime)[0][0]
        i2 = np.nonzero(epoch.value <= state.selectionEnd.datetime)[0][-1]
        epoch = (
          epoch[i1 - self.settings.additionalPoints:i2
                + self.settings.additionalPoints + 1]
        )
      if epoch is not None:
        epochs.update(epoch.datetime)
      if atts is not None and epochatts is None:
        epochatts = atts
    # sort epochs
    epochs = list(epochs)
    epochs.sort()
    # save as astropy time
    epochs = Time(epochs, format="datetime")
    epochs.format = "iso"

    if self.settings.fileFormat == "cdf":
      cdf_spec = {}
      if self.settings.compress:
        cdf_spec["Compressed"] = self.settings.compressionLevel
      with CDF(path, cdf_spec=cdf_spec, delete=True) as cdf:
        spec = {
          "Variable": "epoch",
          "Data_Type": CDF.CDF_EPOCH,
          "Num_Elements": 1,
          "Rec_Vary": True,
          "Var_Type": "zVariable",
          "Dim_Sizes": [1],
          "Sparse": "no_sparse"
        }
        # convert astropy time to epoch list
        epochs.format = "ymdhms"
        dates = np.zeros((len(epochs), 6))
        dates[:, 0] = epochs.value["year"]
        dates[:, 1] = epochs.value["month"]
        dates[:, 2] = epochs.value["day"]
        dates[:, 3] = epochs.value["hour"]
        dates[:, 4] = epochs.value["minute"]
        dates[:, 5] = epochs.value["second"]
        cdf.write_var(
          spec,
          var_attrs=epochatts,
          var_data=cdfepoch.compute_epoch(dates.tolist(), to_np=True)
        )
        epochs.format = "datetime"

        item: Dict[str, Any]
        for item in self.forEachVarToSave(state, epochs):
          spec = {
            "Variable": item["name"],
            "Data_Type": CDF.CDF_FLOAT,
            "Num_Elements": 1,
            "Rec_Vary": True,
            "Var_Type": "zVariable",
            "Dim_Sizes": item["dim"],
            "Sparse": "no_sparse",
          }
          if "FILLVAL" not in item["atts"]:
            maxVal = max(item["data"])
            if maxVal >= 100:
              magnitude = 0
              while maxVal > 1:
                if maxVal > 1e1000:
                  magnitude += 1000
                  maxVal /= 1e1000
                  continue
                if maxVal > 1e100:
                  magnitude += 100
                  maxVal /= 1e100
                  continue
                if maxVal > 1e10:
                  magnitude += 10
                  maxVal /= 1e10
                  continue
                magnitude += 1
                maxVal /= 10
              fill = float(10**(magnitude + 1))
            else:
              fill = 1000
            item["atts"]["FILLVAL"] = fill
            item["data"][np.isnan(item["data"])] = fill

          if "DEPEND_1" in item["atts"]:
            del item["atts"]["DEPEND_1"]
          if "DEPEND_2" in item["atts"]:
            del item["atts"]["DEPEND_2"]
          if "DEPEND_3" in item["atts"]:
            del item["atts"]["DEPEND_3"]
          cdf.write_var(spec, var_attrs=item["atts"], var_data=item["data"])
    elif self.settings.fileFormat == "text":
      names = (([name + "X", name + "Y", name
                 + "Z"] if i == "magField" else [name])
               for (name, i) in ((getattr(self.settings.varNames, i), i)
                                 for i in varnames
                                 if i in self.settings.exportVars))
      names = [i for sublist in names for i in sublist]
      dtype = [(i, "float") for i in names]
      dtype.insert(0, ("date", "U23"))
      numberFormat = ["%.18e" for _ in range(len(names))]
      numberFormat.insert(0, "%s")

      arr = np.zeros(len(epochs), dtype=dtype)
      arr["date"] = epochs.isot
      units = ["UTC"]
      descriptions = []
      item: Dict[str, Any]
      for item in self.forEachVarToSave(state, epochs):
        arr[item["name"]] = item["data"]
        units.append(item["atts"]["UNITS"][0])
        if "CATDESC" in item["atts"]:
          descriptions.append(item["atts"]["CATDESC"][0])
        elif "FIELDNAM" in item["atts"]:
          descriptions.append(item["atts"]["FIELDNAM"][0])
      delimiter = self.settings.fieldDelimiter
      np.savetxt(
        path,
        arr,
        fmt=numberFormat,
        delimiter=delimiter,
        header=delimiter.join(i[0]
                              for i in dtype) + "\n" + delimiter.join(units),
        footer="Variable descriptions:\n" + "\n".join(descriptions)
      )

    doneCallback()

  def cancel(self):
    self.canceled = True

  def showResults(self, window: Toplevel):
    """Called when the user wants to see the results"""
    ttk.Label(window, text="The result is: 42").grid(sticky="nsew")
    window.title(self.name)

  def secondsToMultiUnit(self, s: float):
    m = s // 60
    h = m // 60
    d = h // 24
    s %= 60
    m %= 60
    h %= 24
    intervalList = []
    if d > 0:
      intervalList.append(f"{int(d)}d")
    if h > 0:
      intervalList.append(f"{int(h)}h")
    if m > 0:
      intervalList.append(f"{int(m)}m")
    if s > 0:
      intervalList.append(f"{round(s, 3)}s")
    if len(intervalList) == 0:
      intervalList.append(f"{self.intervalSecs} s")
    return " ".join(intervalList)

  def settingsRangeVarChanged(self, a, b, c):
    self.settings.rangeVariable = self.tkRangeVar.get()

  def settingsAdditionalRangeValidator(
    self, action: str = None, newVal: str = None
  ):
    if newVal is None:
      newVal = self.additionalPointsSpinbox.get()
    if len(newVal) == 0:
      newVal = "0"
    if not re.fullmatch(r"\d+", newVal):
      return False
    newVal = int(newVal)
    maximum = self.additionalPointsSpinbox["to"]
    if newVal > maximum:
      newVal = maximum
      self.additionalPointsSpinbox.set(newVal)
    secs = newVal * self.intervalSecs
    start = self.settingsState.selectionStart - TimeDelta(secs, format="sec")
    end = self.settingsState.selectionEnd + TimeDelta(secs, format="sec")
    text = ((self.secondsToMultiUnit(secs) if secs > 0 else "0s")
            + f"\nStart: {start}\nEnd: {end}")
    self.additionalPointsLabel["text"] = text
    self.settings.additionalPoints = int(newVal)
    if action == "key" or action is None:
      self.tkRangeVar.set("more")
    return True

  def settingsVarCheckbuttonChanged(self, name: str, a, b, c):
    variable = self.settingsExportEnabledTkVariables[name]
    if variable.get() == 1:
      if name not in self.settings.exportVars:
        self.settings.exportVars.add(name)
    elif name in self.settings.exportVars:
      self.settings.exportVars.remove(name)

  def settingsExportNameChanged(self, name: str, a, b, c):
    self.settingsExportEnabledTkVariables[name].set(1)
    setattr(
      self.settings.varNames,
      name,
      self.settingsExportNameTkVariables[name].get().strip()
    )

  def settingsExportMagAsVectorChanged(self, a, b, c):
    self.settings.exportMagAsVector = (
      self.settingsExportMagAsVektorTkVariable.get() == 1
    )
    if "magField" not in self.settings.exportVars:
      self.settings.exportVars.add("magField")

  def settingsFileFormatChanged(self, a, b, c):
    self.settings.fileFormat = self.settingsFileFormatTkVariable.get()
    self.settingsCompressionLevelWidget["state"] = (
      "readonly" if self.settings.fileFormat == "cdf" else "disabled"
    )
    self.settingsFieldDelimiterEntryWidget["state"] = (
      "normal" if self.settings.fileFormat == "text" else "disabled"
    )
    self.settingsFieldDelimiterTabButton["state"] = (
      "normal" if self.settings.fileFormat == "text" else "disabled"
    )

  def settingsCompressChanged(self, a, b, c):
    self.settings.compress = self.settingsCompressTkVariable.get() == 1

  def settingsCompressionLevelChanged(self, a, b, c):
    self.settings.compressionLevel = int(
      self.settingsCompressionLevelTkVariable.get()
    )

  def settingsValidateFillValue(self, action: str, newVal: str):
    self.settings.fillValue = newVal
    return True

  def settingsValidateFieldDelimiter(self, action: str, newVal: str):
    if action == "key" and len(newVal) > 1:
      return False
    self.settings.fieldDelimiter = newVal
    self.settingsFieldDelimiterDisplayWidget["text"] = (
      '>"<' if newVal == '"' else f'"{newVal}"'
    )
    return True

  def onSettingsClose(self, event):
    if not isinstance(event.widget, tk.Toplevel):
      return
    self.checkAllVariablesHaveName()

  def checkAllVariablesHaveName(self):
    missing = [
      selectedVarNameLookup[name]
      for name in varnames
      if len(getattr(self.settings.varNames, name).strip()) == 0
    ]
    if len(missing) > 0:
      showwarning(
        f"{self.name} - IMARR",
        "The variable name{pluralS} of the variable{pluralS}\n\n{}\n\n{verb} set to an empty value!"
        .format(
          '\n'.join(missing),
          pluralS="s" if len(missing) > 1 else "",
          verb="are" if len(missing) > 1 else "is"
        )
      )
      return False
    return True

  def getData(self, state: State, cdf: CDFRead, epochs: Time, name: str):
    atts = cdf.varattsget(name, expand=True)
    epoch = cdfastropy.convert_to_astropy(
      cdf.varget((atts["DEPEND_0"] or ["epoch"])[0])
    )
    epoch.format = "datetime"

    if self.settings.rangeVariable == "all":
      start, end = None, None
    elif self.settings.rangeVariable == "selected":
      start = TimeToList(state.selectionStart)
      end = TimeToList(state.selectionEnd)
    elif self.settings.rangeVariable == "more":
      i1 = np.nonzero(epoch.value >= state.selectionStart.datetime)[0][0]
      i2 = np.nonzero(epoch.value <= state.selectionEnd.datetime)[0][-1]
      start = TimeToList(epoch[i1 - self.settings.additionalPoints])
      end = TimeToList(epoch[i2 + self.settings.additionalPoints])

    data = np.array(cdf.varget(name, starttime=start, endtime=end))
    setFillValuesToNan(data, atts)
    if data.shape[0] == len(epochs):
      return data, atts

    shape = (len(epochs), )
    if len(data.shape) > 1:
      shape += (data.shape[1], )
    retData = np.full(shape, np.nan)
    retData[np.isin(epochs.datetime, epoch.value), :] = data
    return retData, atts

  def forEachVarToSave(self, state: State, epochs: Time):
    for name in varnames:
      if name not in self.settings.exportVars:
        continue

      selectedVar = state.selectedVars[selectedVarNameLookup[name]]
      if name == "magField":
        vectorData = None
        vectorAtts = None
        for index, dir in enumerate(["x", "y", "z"]):
          selected = next((i for i in selectedVar if i.Bfield == dir), None)
          if selected is None:
            selected = next((i for i in selectedVar if i.Bfield == "vector"),
                            None)
          if selected is None:
            continue

          cdfReader = state.datasetCDFInstances[selected.dataset]
          data, atts = self.getData(state, cdfReader, epochs, selected.variable)
          if len(data.shape) > 1:
            data = data[:, index]

          if (self.settings.fileFormat == "cdf"
              and self.settings.exportMagAsVector):
            if vectorData is None:
              vectorData = np.full((len(data), 3), np.nan)
              vectorAtts = atts
            vectorData[:, index] = data
          else:
            yield {
              "name": getattr(self.settings.varNames, name) + dir.upper(),
              "dim": [1],
              "atts": atts,
              "data": data
            }

        # save vector
        if (self.settings.fileFormat == "cdf"
            and self.settings.exportMagAsVector):
          yield {
            "name": getattr(self.settings.varNames, name),
            "dim": [3],
            "atts": vectorAtts,
            "data": vectorData
          }
      else:
        if name == "magFieldTotal":
          selected = next((i for i in selectedVar if i.Bfield == "total"), None)
        else:
          selected = next((i for i in selectedVar), None)
        if selected is None:
          continue

        cdfReader = state.datasetCDFInstances[selected.dataset]
        data, atts = self.getData(state, cdfReader, epochs, selected.variable)

        yield {
          "name": getattr(self.settings.varNames, name),
          "dim": [1],
          "atts": atts,
          "data": data
        }


def TimeToList(time: Time):
  return [
    time.ymdhms["year"],
    time.ymdhms["month"],
    time.ymdhms["day"],
    time.ymdhms["hour"],
    time.ymdhms["minute"],
    time.ymdhms["second"]
  ]
