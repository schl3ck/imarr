import tkinter as tk
from tkinter import ttk
from astropy.time import Time, TimezoneInfo
from astropy.units import hour as unitHour
import json
from typing import Callable, Dict, Union, List
from functools import partial, reduce
import cdflib

from src.pages.BasePage import BasePage
from src.utils.utils import ensureOnScreen
from src.utils.cache import Cache
from src.utils import CDFCache
from src.utils.constants import (padding, cdas)
from src.utils.State import State


class DownloadDataFiles(BasePage):
  skipOnBackward = True

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

    # yapf: disable
    self.datasetFileResults: (Dict[str, Union[Exception,
                                              int,
                                              Dict[str, int]]]) = {}
    # yapf: enable
    self.datasetCDFData: Dict[str, Union[cdflib.cdfread.CDF, Exception]] = (
      state.datasetCDFInstances or {}
    )
    self.datasetDataCache: Dict[str, Cache] = {}
    self.datasetVariables: Dict[str, List[str]] = {}
    self.datasetDownloadProgress: Dict[str, float] = {}
    for dataset in state.datasets:
      variables = [
        v.variable
        for var in state.selectedVars.values()
        for v in var
        if v.dataset == dataset.id
      ]
      if len(variables) > 0:
        self.datasetVariables[dataset.id] = variables
        self.datasetDataCache[dataset.id] = Cache(
          "data_filename_{}_{}_{}_{}".format(
            dataset.id,
            "-".join(variables),
            state.startDate.isot,
            state.endDate.isot
          ),
          False
        )

    master.title("Data download - IMARR")

    self.createStatusLabel()
    self.pack(fill="both")
    self.bind("<Visibility>", self.loaded)

  def loaded(self, event):
    """
    Called, once the window is shown. Flushes any queued drawing and
    loads the data files.
    """
    self.update_idletasks()

    # resize contents
    width = self.winfo_width() - padding
    self.pbStatus["length"] = width

    self.update_idletasks()
    ensureOnScreen(self.master)

    if (len(self.datasetCDFData) > 0
        and all(dataset.id in self.datasetCDFData
                for dataset in self.state.datasets)):
      self.downloadDone()
    else:
      self.getFileURLs()

  def createStatusLabel(self):
    self.controlsFrame = tk.Frame(self)
    self.controlsFrame.grid(column=2, row=1, sticky="ns")
    self.contentFrame = tk.Frame(self.controlsFrame)
    self.contentFrame.pack(side="top", anchor="n", fill="y")
    self.navigationFrame = tk.Frame(self.controlsFrame)
    self.navigationFrame.pack(side="bottom", anchor="s", fill="x")

    self.lbStatus = ttk.Label(
      self.contentFrame, text="Loading...", justify="left"
    )
    self.lbStatus.grid(column=1, row=1, padx=padding, pady=padding, sticky="w")

    self.pbStatus = ttk.Progressbar(self.contentFrame, orient="horizontal")
    self.pbStatus.grid(column=1, row=2, padx=padding, pady=padding, sticky="we")

    self.bBack = ttk.Button(
      self.navigationFrame,
      text="Back",
      command=partial(self.goDirection, "back")
    )
    self.bBack.pack(
      side="left", fill="x", expand=True, pady=padding, padx=padding
    )

    self.bContinue = ttk.Button(
      self.navigationFrame,
      text="Continue",
      command=partial(self.goDirection, "forward")
    )
    # self.bContinue.pack(
    #   side="left", fill="x", expand=True, pady=padding
    # )

  def getFileURLs(self):
    utcTimezone = TimezoneInfo(utc_offset=0 * unitHour)
    print(
      "getting data between {} and {}".format(
        self.state.startDate.to_datetime(timezone=utcTimezone),
        self.state.endDate.to_datetime(timezone=utcTimezone)
      )
    )

    def load(dataset):
      return cdas.get_data_file(
        dataset,
        self.datasetVariables[dataset],
        self.state.startDate.to_datetime(timezone=utcTimezone),
        self.state.endDate.to_datetime(timezone=utcTimezone)
      )

    def done(dataset, fromCache, dataResult):
      if dataResult:
        if 200 <= dataResult[0] < 300:
          self.datasetFileResults[dataset] = dataResult[1]
        else:
          self.datasetFileResults[dataset] = dataResult[0]
      if len(self.datasetFileResults) == len(self.datasetDataCache):
        if fromCache:
          self.allFileURLsLoaded()
        else:
          self.after(1, self.allFileURLsLoaded)

    self.pbStatus["mode"] = "indeterminate"
    self.pbStatus.start()
    for dataset, cache in self.datasetDataCache.items():
      cache.get(
        partial(load, dataset),
        partial(done, dataset),
        onError=partial(done, dataset, False)
      )

  def allFileURLsLoaded(self):
    failed = [
      "{}: {}".format(dataset, res)
      for (dataset, res) in self.datasetFileResults.items()
      if isinstance(res, (Exception, int))
    ]
    if len(failed) > 0:
      failed = "\n".join(failed)
      self.lbStatus["text"] = (
        f"""Could not load the data for the dataset(s)

{failed}

Please check your internet connection, restart the program or try again later.
If this error persists, please check for a new version of this program or contact the developer."""
      )
      self.pack(padx=padding * 2, pady=padding * 2)
      return

    self.pbStatus.stop()
    self.pbStatus["value"] = 0.
    # print(json.dumps(self.datasetFileResults, indent=2))

    self.downloadFiles()

  def downloadFiles(self):
    def done(dataset, fromCache, result: Exception):
      if fromCache is None:
        print("error loading file: {}".format(result))
      self.datasetCDFData[dataset] = result

    def progress(val, status, dataset):
      self.datasetDownloadProgress[dataset] = val
      return 0

    self.pbStatus["value"] = 0.
    self.pbStatus["mode"] = "determinate"

    for (dataset, fileResult) in self.datasetFileResults.items():
      print(
        "downloading file: {}".format(
          json.dumps(fileResult["FileDescription"], indent=2)
        )
      )
      self.datasetDownloadProgress[dataset] = 0.
      CDFCache.get(
        fileResult["FileDescription"],
        partial(done, dataset),
        partial(done, dataset, None),
        progressCallback=progress,
        progressUserValue=dataset
      )

    def checkProgress():
      total = reduce(
        lambda acc, cur: acc + cur, self.datasetDownloadProgress.values(), 0
      ) * 100 / len(self.datasetDownloadProgress)
      self.pbStatus["value"] = total
      self.lbStatus["text"] = "Loading... {:.2f}%".format(total)
      if len(self.datasetCDFData) == len(self.datasetFileResults):
        self.after(1, self.downloadDone)
      else:
        self.after(50, checkProgress)

    checkProgress()

  def downloadDone(self):
    self.goDirection("forward")

  def goDirection(self, dir: str):
    state = self.state.copy()
    state.datasetCDFInstances = self.datasetCDFData.copy()
    self.pageHandler(dir, state)

  def buildState(self):
    # don't add anything since the datasets aren't downloaded yet. if they were,
    # we weren't here anymore
    return self.state

  @staticmethod
  def stateSufficient(state: State):
    needed = ["observatory", "startDate", "endDate", "datasets", "selectedVars"]
    return all(state.has(i) for i in needed)
