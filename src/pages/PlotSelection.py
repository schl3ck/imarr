from matplotlib.lines import Line2D
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from astropy.time import Time
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import AutoMinorLocator
from matplotlib.dates import DateFormatter
from matplotlib.backend_bases import MouseEvent
from matplotlib.axes import Axes
import numpy as np
from typing import Callable, Dict, Tuple, Union, List
from functools import partial
import cdflib

from src.pages.BasePage import BasePage
from src.utils.ScrollableFrame import ScrollableFrame
from src.utils.MatplotlibTkinterIntegration import createPlot
from src.utils.cache import Cache
from src.utils.constants import (padding, requiredVariables, optionalVariables)
from src.utils.utils import (
  TimeRange2USDateStr, ensureOnScreen, isMacOS, setFillValuesToNan
)
from src.utils.PlotRangeSelection import PlotRangeSelection
from src.utils.State import State, StateSelectedVar

pathYaxisLabels = "src/assets/possibleYaxisLabels.txt"
isoDateFormatter = DateFormatter("%Y-%m-%d %H:%M:%S.%f")


class PlotSelection(BasePage):
  disableSaveHotkey = True

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
    self.possibleYaxisLabels: List[str] = []

    self.selection = {
      "start": self.state.selectionStart, "end": self.state.selectionEnd
    }
    self.selectionHistory: List[Dict[str, Time]] = []
    self.selectionHistoryIndex = -1

    master.title("Plot - Specific Time Range Selection - IMARR")

    self.createStatusLabel()
    self.pack(fill="both")
    self.bind("<Visibility>", self.loaded)

  def loaded(self, event):
    """
    Called, once the frame is shown. Flushes any queued drawing and
    plots the data files.
    """
    self.update_idletasks()

    if len(self.possibleYaxisLabels) == 0:
      self.possibleYaxisLabels = self.loadYaxisKeys()

    vars: List[StateSelectedVar] = []
    for variableGroups in [requiredVariables, optionalVariables]:
      for variableGroup in variableGroups:
        if self.state.selectedVars[variableGroup]:
          vars.extend(self.state.selectedVars[variableGroup])
    self.checkYaxisLabel(vars)

  def checkYaxisLabel(self, vars: List[StateSelectedVar]):
    if len(vars) == 0:
      self.update_idletasks()
      self.plotData()
      return

    for i, var in enumerate(vars):
      cdf = self.state.datasetCDFInstances[var.dataset]
      cdfInfo = cdf.cdf_info()
      if (var.variable in cdfInfo["zVariables"]
          or var.variable in cdfInfo["rVariables"]):
        yAttrs = cdf.varattsget(var.variable)
        if any(key in yAttrs for key in self.possibleYaxisLabels):
          continue
        # no key found
        self.askYaxisLabel(vars[i:], yAttrs)
        return

    # all keys found
    self.plotData()

  def createStatusLabel(self):
    self.controlsFrame = tk.Frame(self)
    self.controlsFrame.grid(column=2, row=1, sticky="ns")
    self.contentFrame = tk.Frame(self.controlsFrame)
    self.contentFrame.pack(side="top", anchor="n", fill="y")
    self.navigationFrame = tk.Frame(self.controlsFrame)
    self.navigationFrame.pack(side="bottom", anchor="s", fill="x", padx=padding)

    self.lbStatus = ttk.Label(
      self.contentFrame, text="Loading...", justify="left"
    )
    self.lbStatus.grid(column=1, row=1, padx=padding, pady=padding, sticky="w")

    self.bBack = ttk.Button(
      self.navigationFrame,
      text="Back",
      command=partial(self.goDirection, "back")
    )
    self.bBack.pack(side="left", fill="x", expand=True, pady=padding)

    self.bContinue = ttk.Button(
      self.navigationFrame,
      text="Continue",
      command=partial(self.goDirection, "forward")
    )
    # self.bContinue.pack(
    #   side="left", fill="x", expand=True, pady=padding
    # )

  def askYaxisLabel(self, vars: List[StateSelectedVar], yAttrs: dict):
    var = vars[0]
    self.lbStatus[
      "text"] = f"Please select the Y axis label for variable {var.variable}"

    frame = ScrollableFrame(self.contentFrame, ttk.Frame, width=500, height=600)
    frame.grid(column=1, row=2, sticky="we")

    radioVar = tk.StringVar("")
    for i, (key, value) in enumerate(yAttrs.items()):
      radio = ttk.Radiobutton(
        frame.innerFrame, variable=radioVar, value=key, text=f"{key}: {value}"
      )
      radio.grid(column=1, row=i, padx=padding, sticky="w")

    def onContinue():
      if radioVar.get() == "":
        messagebox.showerror(
          "No label selected", "Please select a label to continue"
        )
        return
      frame.grid_forget()
      self.possibleYaxisLabels.append(radioVar.get())
      self.saveYaxisKeys()
      self.checkYaxisLabel(vars[1:])

    self.bContinue["command"] = onContinue
    self.bContinue.pack(side="left", fill="x", expand=True, pady=padding)

    self.update_idletasks()
    frame.canvas["height"] = min(frame.innerFrame.winfo_height(), 600)
    frame.canvas["width"] = frame.innerFrame.winfo_width()
    ensureOnScreen(self.master)

  def plotData(self):
    self.update_idletasks()

    # inches
    axHeight = 1
    titleHeight = 0.55
    xLabelHeight = 0.7

    # plot data
    vars: List[StateSelectedVar] = []
    for variableGroups in [requiredVariables, optionalVariables]:
      for variableGroup in variableGroups:
        if self.state.selectedVars[variableGroup]:
          vars.extend(self.state.selectedVars[variableGroup])

    datasetOrder = []
    # height in inches
    figureSubplotHeight = []
    for var in vars:
      if var.dataset not in datasetOrder:
        datasetOrder.append(var.dataset)
        figureSubplotHeight.append(0)
      # add single axis height to last entry
      figureSubplotHeight[-1] += axHeight

    figureTotalSubplotHeight = sum(figureSubplotHeight)
    figureAverageSubplotHeight = (
      figureTotalSubplotHeight / len(figureSubplotHeight)
    )
    figureTotalHeight = (
      figureTotalSubplotHeight + len(figureSubplotHeight) *
      (titleHeight + xLabelHeight)
    )

    fig = plt.figure(figsize=(6.4, figureTotalHeight))
    parentGrid = GridSpec(
      len(datasetOrder),
      1,
      fig,
      top=1 - (titleHeight / figureTotalHeight),
      right=0.97,
      bottom=xLabelHeight / figureTotalHeight,
      left=0.15,
      hspace=(titleHeight + xLabelHeight) / figureAverageSubplotHeight,
      height_ratios=[i / figureTotalSubplotHeight for i in figureSubplotHeight]
    )
    firstAx = None
    self.allPlotAxes: List[Axes] = []
    allPlotLines: List[List[Line2D]] = []
    totalXmin = None
    totalXmax = None
    self.xDataTime: Time = None

    for i, dataset in enumerate(datasetOrder):
      varsToPlot = [var for var in vars if var.dataset == dataset]
      childGridItem = parentGrid[i].subgridspec(len(varsToPlot), 1, hspace=0)
      axs = None
      if firstAx is None:
        axs = childGridItem.subplots(sharex=True)
        firstAx = axs[0]
      else:
        axs = [
          childGridItem.figure.add_subplot(childGridItem[i, 0], sharex=firstAx)
          for i in range(len(varsToPlot))
        ]
      lastIndex = len(varsToPlot) - 1
      if not isinstance(axs, (list, np.ndarray)):
        axs = [axs]

      self.allPlotAxes.extend(axs)

      # set dataset title
      title = next((d.label for d in self.state.datasets if d.id == dataset),
                   "Unknown dataset")
      axs[0].set_title(
        title,
        fontdict={
          "fontsize":
            "large" if len(title) <= 100 else
            ("normal" if len(title) <= 150 else "small")
        },
        wrap=True
      )

      cdf = self.state.datasetCDFInstances[dataset]
      cdfInfo = cdf.cdf_info()
      firstVar = next((
        i.variable for i in varsToPlot if i.variable in cdfInfo["rVariables"]
        or i.variable in cdfInfo["zVariables"]
      ),
                      None)
      firstAttsDepend0 = (
        cdf.varattsget(firstVar)["DEPEND_0"] if firstVar is not None else None
      )
      xData = cdflib.cdfastropy.convert_to_astropy(
        cdf.varget(firstAttsDepend0 or "epoch")
      )
      if self.xDataTime is None:
        self.xDataTime = xData
      totalXmin = (
        xData[0].datetime
        if totalXmin is None else min(totalXmin, xData[0].datetime)
      )
      totalXmax = (
        xData[-1].datetime
        if totalXmax is None else max(totalXmax, xData[-1].datetime)
      )

      axs[-1].set_xlabel(
        "Time (UTC, {})".format(
          TimeRange2USDateStr(xData[0].datetime, xData[-1].datetime)
        )
      )

      for i2, (var, ax) in enumerate(zip(varsToPlot, axs)):
        if (var.variable in cdfInfo["zVariables"]
            or var.variable in cdfInfo["rVariables"]):
          yData = cdf.varget(var.variable)
          yAttrs = cdf.varattsget(var.variable)
          isVector = len(yData.shape) > 1 and yData.shape[1] > 1
          setFillValuesToNan(yData, yAttrs)
          if isVector:
            fmts = ["-r", "--g", ":b"]
            labels = ["X", "Y", "Z"]
            lines = []
            for dim in range(yData.shape[1]):
              lines.extend(
                ax.plot(
                  xData.datetime,
                  yData[:, dim],
                  fmts[dim],
                  linewidth=1,
                  label=labels[dim]
                )
              )
            allPlotLines.append(lines)
            ax.legend(loc="upper right")
          else:
            allPlotLines.append(
              ax.plot(xData.datetime, yData, "-k", linewidth=1)
            )
          # yapf: disable
          ax.set_ylabel(
            next(
              (yAttrs[key] for key in self.possibleYaxisLabels if key in yAttrs),
              "Label not found"
            )
            + (
              " [{}]".format(yAttrs["UNITS"])
              if "UNITS" in yAttrs and str(yAttrs["UNITS"]).lower() != "na"
              else ""
            ),
            wrap=True
          )
          # yapf: enable

          # plot horizontal line at y=axlineY only when data crosses it
          # at y=1 for plasma beta, else at y=0
          axlineY = (1 if var in self.state.selectedVars.Plasma_Beta else 0)
          if np.nanmin(yData) < axlineY and np.nanmax(yData) > axlineY:
            ax.axhline(y=axlineY, linewidth=1, color="k")
          if axlineY == 1:
            ax.set_yscale("log")
        else:
          # variable not in data
          ax.text(
            0.5,
            0.5,
            "Variable '{}' was not found in the data".format(var.variable),
            verticalalignment='center',
            horizontalalignment='center',
            transform=ax.transAxes,
            wrap=True
          )
          allPlotLines.append([])

        ax.fmt_xdata = isoDateFormatter
        # axes customisation
        majorLoc = ax.xaxis.get_major_locator()
        ticks: List[float] = majorLoc()
        diff = ticks[1] - ticks[0]
        possibleIntervals = [
          1 / 24 / 60,    # 1 min
          1 / 24 / 12,    # 5 min
          1 / 24 / 6,    # 10 min
          1 / 24 / 4,    # 15 min
          1 / 24 / 2,    # 30 min
          1 / 24,    # 1 h
          1 / 12,    # 2 h
          1 / 8,    # 3 h
          1 / 4,    # 6 h
          1 / 2,    # 12 h
          1,    # 1 d
          2,
          5,
          10
        ]
        multiple = 5
        for i in possibleIntervals:
          m = diff // i
          if m in [2, 4, 5, 6]:
            multiple = m
            break
        ax.xaxis.set_minor_locator(AutoMinorLocator(multiple))
        ax.xaxis.set_major_formatter(DateFormatter("%d\n%H%M"))
        if ax.get_yscale() == "linear":
          ax.yaxis.set_minor_locator(AutoMinorLocator(5))
        if i2 == 0 and i2 == lastIndex:
          ax.tick_params(
            axis="x",
            which="major",
            direction="inout",
            length=10,
            bottom=True,
            labelbottom=True
          )
          ax.tick_params(
            axis="x", which="major", direction="in", length=5, top=True
          )
          ax.tick_params(
            axis="x", which="minor", direction="inout", length=5, bottom=True
          )
          ax.tick_params(
            axis="x", which="minor", direction="in", length=2.5, top=True
          )
        else:
          ax.tick_params(
            axis="x",
            which="major",
            direction="inout" if i2 == lastIndex else "in",
            length=10 if i2 == lastIndex else 5,
            bottom=True,
            top=True,
            labelbottom=i2 == lastIndex
          )
          ax.tick_params(
            axis="x",
            which="minor",
            direction="inout" if i2 == lastIndex else "in",
            length=5 if i2 == lastIndex else 2.5,
            bottom=True,
            top=True
          )
        ax.tick_params(
          axis="y",
          which="major",
          direction="out",
          length=10,
          left=True,
          right=False,
          labelleft=True,
        )
        ax.tick_params(
          axis="y",
          which="minor",
          direction="out",
          length=5,
          left=True,
          right=False
        )

    # display the plot & controls

    self.lbStatus.grid_remove()

    self.plotFrame = tk.Frame(self)
    self.scrollableFrame = ScrollableFrame(self.plotFrame, ttk.Frame)
    self.canvasFrame = self.scrollableFrame.innerFrame

    (self.plotCanvas, self.plotToolbar) = createPlot(
      self.plotFrame, fig, canvasMaster=self.canvasFrame
    )
    plotSize = self.plotCanvas.get_width_height()
    self.scrollableFrame.canvas["width"] = plotSize[0]
    self.scrollableFrame.canvas["height"] = min(
      plotSize[1], self.plotFrame.winfo_screenheight() * 0.88
    )

    self.plotRangeSelection = PlotRangeSelection(
      self.allPlotAxes, self.plotCanvas, (totalXmin, totalXmax)
    )
    self.plotRangeSelection.onSelection.append(self.onSelection)

    self.checkMPLToolbarMode()

    # set max width of lable to wrap
    self.lbStatus["wraplength"] = (plotSize[0] / 2) - 2 * padding

    varRangeSelectionLock = tk.IntVar(self)
    self.btnToggleRangeSelectionLock = ttk.Checkbutton(
      self.contentFrame,
      text="Lock selection (only needed when saving the plot)",
      variable=varRangeSelectionLock,
      command=self.toggleRangeSelection,
      onvalue=1,
      offvalue=0,
      state=tk.DISABLED
    )
    self.btnToggleRangeSelectionLock.var = varRangeSelectionLock

    self.lbSelectionStartLabel = ttk.Label(
      self.contentFrame, text="Selection start:"
    )
    self.lbSelectionStartValue = ttk.Label(self.contentFrame, text="0")
    self.lbSelectionEndLabel = ttk.Label(
      self.contentFrame, text="Selection end:"
    )
    self.lbSelectionEndValue = ttk.Label(self.contentFrame, text="0")

    self.fHistoryButtons = ttk.Frame(self.contentFrame)
    self.btnSelectionUndo = ttk.Button(
      self.fHistoryButtons,
      command=self.selectionUndo,
      text="Undo",
      state=tk.DISABLED
    )
    self.btnSelectionRedo = ttk.Button(
      self.fHistoryButtons,
      command=self.selectionRedo,
      text="Redo",
      state=tk.DISABLED
    )

    # display value under cursor
    self.fValueDisplay = ttk.Frame(self.contentFrame)
    self.lbValues: Dict[Union[Tuple[str, str], str], ttk.Label] = {}
    label = ttk.Label(self.fValueDisplay, text="Time:")
    label.grid(column=1, row=0, padx=padding, pady=padding, sticky="w")
    lbValue = ttk.Label(self.fValueDisplay, text="")
    lbValue.grid(column=2, row=0, pady=padding, sticky="w")
    self.lbValues["x"] = lbValue
    for i, var in enumerate(vars):
      label = ttk.Label(self.fValueDisplay, text=var.variable + ":")
      label.grid(column=1, row=i + 1, padx=padding, pady=padding, sticky="w")
      lbValue = ttk.Label(self.fValueDisplay, text="")
      lbValue.grid(column=2, row=i + 1, pady=padding, sticky="w")
      lbValue.lines = allPlotLines[i]
      self.lbValues[(var.dataset, var.variable)] = lbValue
    self.plotCanvas.mpl_connect("motion_notify_event", self.onMouseMove)

    self.lbStatus.grid(
      column=1,
      row=1,
      columnspan=2,
      padx=padding,
      pady=padding,
      sticky="w",
    )
    self.btnToggleRangeSelectionLock.grid(
      column=1, row=2, columnspan=2, padx=padding, pady=padding, sticky="we"
    )
    self.lbSelectionStartLabel.grid(column=1, row=3, padx=padding, sticky="w")
    self.lbSelectionStartValue.grid(column=2, row=3, padx=padding, sticky="w")
    self.lbSelectionEndLabel.grid(column=1, row=4, padx=padding, sticky="w")
    self.lbSelectionEndValue.grid(column=2, row=4, padx=padding, sticky="w")
    self.fHistoryButtons.grid(
      column=1, row=5, columnspan=2, padx=padding, sticky="we"
    )
    self.btnSelectionUndo.pack(side="left", fill="x", expand=True)
    self.btnSelectionRedo.pack(side="left", fill="x", expand=True)
    self.fValueDisplay.grid(column=1, row=6, columnspan=2, sticky="we")

    # self.pack_forget()
    self.bContinue.pack(side="left", fill="x", expand=True, pady=padding)

    self.plotFrame.grid(column=1, row=1, sticky="n")
    self.plotToolbar.grid(column=1, row=1, sticky="we")
    self.scrollableFrame.grid(column=1, row=2)
    self.plotCanvas.get_tk_widget().grid(column=1, row=1)

    if self.selection["start"] or self.selection["end"]:
      self.plotRangeSelection.setSelection(
        self.selection["start"], self.selection["end"]
      )
    self.onSelection(self.selection["start"], self.selection["end"], False)

    self.registerHistoryHotkeys()
    ensureOnScreen(self.master)

  def checkMPLToolbarMode(self):
    """Checks every 50 ms if the mode of the toolbar has changed to
    disable/enable plotRangeSelection and set the correct status text
    """
    # HACK: matplotlib.backends.backend_tkagg.NavigationToolbar2Tk
    # attribute "mode" is not documented and therefore probabyl internal.
    # maybe in the future there will be a documented attribute to get the mode
    self.plotRangeSelection.enabled = (
      self.plotToolbar.mode == self.plotToolbar.mode.NONE
    )
    self.lbStatus["text"] = (
      "Please select the start time (left click) and end time (right click) by "
      "clicking into the plot or clicking and dragging with the left mouse "
      "button"
    ) if self.plotRangeSelection.enabled else (
      "Disable any pan and zoom buttons to select the start and end time"
    )
    self.lbStatus["background"] = (
      "red" if not self.plotRangeSelection.enabled else ""
    )
    self.after(50, self.checkMPLToolbarMode)

  def onMouseMove(self, event: MouseEvent):
    if event.xdata is None:
      return
    xValue = np.nan
    time = None
    for vars in self.state.selectedVars.values():
      for var in vars:
        label = self.lbValues[(var.dataset, var.variable)]
        xyData = [line.get_xydata() for line in label.lines]
        selector = [np.nonzero(data[:, 0] == event.xdata)[0] for data in xyData]
        if any(len(i) == 0 and any(data[:, 0] < event.xdata) for i,
               data in zip(selector, xyData)):
          lastLess = [
            np.nonzero(data[:, 0] < event.xdata)[0][-1] for data in xyData
          ]
          if any(i + 1 < data.shape[0] for i, data in zip(lastLess, xyData)):
            selector = [(
              less if abs(data[less, 0] - event.xdata) <
              abs(data[less + 1, 0] - event.xdata) else less + 1
            ) for (data, less) in zip(xyData, lastLess)]
          else:
            selector = [[] for i in lastLess]
        yData = [
          str(data[i, 1]).replace("[]", "") for data,
          i in zip(xyData, selector)
        ]
        x = next((data[i, 0] for data, i in zip(xyData, selector)), None)
        if np.isscalar(x) and not np.isnan(x):
          xValue = x
        label["text"] = "\n".join(yData)
    if not np.isnan(xValue):
      time = isoDateFormatter.format_data(xValue)
    self.lbValues["x"]["text"] = time if time is not None else ""

  def toggleRangeSelection(self):
    if self.btnToggleRangeSelectionLock.var.get() == 1:
      self.plotRangeSelection.lock()
    else:
      self.plotRangeSelection.unlock()

  def onSelection(self, start, end, dragging):
    def snap(time: Time):
      if time is None:
        return None
      if time < self.xDataTime.min():
        return self.xDataTime.min()
      if time > self.xDataTime.max():
        return self.xDataTime.max()
      lastLess = np.nonzero(self.xDataTime < time)[0][-1]
      if lastLess + 1 == len(self.xDataTime):
        return self.xDataTime[lastLess]
      t1 = self.xDataTime[lastLess]
      t2 = self.xDataTime[lastLess + 1]
      return t1 if time - t1 < t2 - time else t2

    start = snap(start)
    if start:
      start = start.copy()
      start.format = "iso"
    end = snap(end)
    if end:
      end = end.copy()
      end.format = "iso"

    self.updateSelectionLabels(start, end)
    if not dragging:
      self.plotRangeSelection.setSelection(start, end)
      self.appendToSelectionHistory()
    self.updateHistoryButtons()
    self.bContinue["state"] = (
      tk.NORMAL
      if self.selection["start"] and self.selection["end"] else tk.DISABLED
    )

  def updateSelectionLabels(self, start, end):
    self.btnToggleRangeSelectionLock["state"] = (
      tk.NORMAL if start and end else tk.DISABLED
    )
    self.selection["start"] = start
    self.selection["end"] = end
    self.lbSelectionStartValue["text"] = str(start) if start is not None else ""
    self.lbSelectionEndValue["text"] = str(end) if end is not None else ""

  def appendToSelectionHistory(self):
    if self.selectionHistoryIndex < len(self.selectionHistory) - 1:
      del self.selectionHistory[self.selectionHistoryIndex + 1:]
    self.selectionHistory.append(dict(self.selection))
    self.selectionHistoryIndex += 1
    self.updateHistoryButtons()

  def updateHistoryButtons(self):
    self.btnSelectionUndo["state"] = (
      tk.NORMAL if self.selectionHistoryIndex > 0 else tk.DISABLED
    )
    self.btnSelectionRedo["state"] = (
      tk.NORMAL if self.selectionHistoryIndex < len(self.selectionHistory) - 1
      else tk.DISABLED
    )

  def selectionUndo(self, event=None):
    if self.selectionHistoryIndex <= 0:
      return
    self.selectionHistoryIndex -= 1
    start = self.selectionHistory[self.selectionHistoryIndex]["start"]
    end = self.selectionHistory[self.selectionHistoryIndex]["end"]
    self.updateSelectionLabels(start, end)
    self.updateHistoryButtons()
    self.plotRangeSelection.setSelection(start=start, end=end)

  def selectionRedo(self, event=None):
    if self.selectionHistoryIndex >= len(self.selectionHistory) - 1:
      return
    self.selectionHistoryIndex += 1
    start = self.selectionHistory[self.selectionHistoryIndex]["start"]
    end = self.selectionHistory[self.selectionHistoryIndex]["end"]
    self.updateSelectionLabels(start, end)
    self.updateHistoryButtons()
    self.plotRangeSelection.setSelection(start=start, end=end)

  def registerHistoryHotkeys(self):
    self.historyBindings = {}
    self.historyBindings["undo"] = self.master.bind(
      "<{}-z>".format("Command" if isMacOS() else "Control"),
      self.selectionUndo
    )
    self.historyBindings["redo"] = self.master.bind(
      "<{}-y>".format("Command" if isMacOS() else "Control"),
      self.selectionRedo
    )

  def removeHistoryHotkeys(self):
    if (not hasattr(self, "historyBindings")
        or not isinstance(self.historyBindings, dict)):
      return

    self.master.unbind(
      "<{}-z>".format("Command" if isMacOS() else "Control"),
      self.historyBindings["undo"]
    )
    self.master.unbind(
      "<{}-y>".format("Command" if isMacOS() else "Control"),
      self.historyBindings["redo"]
    )
    self.historyBindings = None

  def goDirection(self, dir: str):
    self.removeHistoryHotkeys()
    state = self.buildState()
    self.pageHandler(dir, state)

  def buildState(self):
    state = self.state.copy()
    state.selectionStart = self.selection["start"]
    state.selectionEnd = self.selection["end"]
    return state

  def loadYaxisKeys(self):
    with open(pathYaxisLabels, "r") as file:
      return [line.strip() for line in file]

  def saveYaxisKeys(self):
    with open(pathYaxisLabels, "w") as file:
      file.write("\n".join(self.possibleYaxisLabels))

  @staticmethod
  def stateSufficient(state: State):
    needed = [
      "observatory",
      "startDate",
      "endDate",
      "datasets",
      "selectedVars",
      "datasetCDFInstances"
    ]
    return all(state.has(i) for i in needed)
