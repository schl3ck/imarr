import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import re
from typing import Callable
from astropy.time import Time, TimeDelta
from functools import partial, reduce

from src.pages.BasePage import BasePage
from src.utils.cache import Cache
from src.utils.constants import (
  padding,
  requestCheckInterval,
  requestMaxRetries,
  cacheFolder,
  cacheFolderNotFolder,
  cdas,
  instrumentTypes,
  navigationButtonInnerPadding
)
from src.utils.utils import (ensureOnScreen, intersection, scrollableTreeview)
from src.utils.State import State

# initialValues:
# {
#   "observatory": str
#   "startDate": str
#   "endDate": str
# }

# TODO: change pack to grid to show label on top on error after reload


class ObservatorySelection(BasePage):
  def __init__(
    self,
    master: tk.Tk,
    pageHandler: Callable[[str, State], None],
    state: State
  ):
    super().__init__(master)
    self.master = master
    self.pageHandler = pageHandler
    self.state = state if isinstance(state, State) else State()
    self.pack()
    # construct a time class once to load the whole lib behind it which takes a bit
    # otherwise the program would freez shortly when a time has to be constructed
    self.after(500, lambda: Time("2021-01-01", format="iso"))

    self.master.title("Observatory and Date Selection - IMARR")

    self.observatoryGroups = None
    self.fObservatoryGroups = None
    self.fObservatories = None
    self.tvObservatoryGroups = None
    self.lbObservatories = None
    self.btnReloadObservatories = None

    self.cache = Cache("observatoryGroups")

    self.createWidgets()
    self.bind("<Visibility>", self.loaded)

  def createWidgets(self):
    """
    Creates the status label that is displayed while loading the
    observatories.
    """
    if cacheFolderNotFolder:
      text = "Please move the file \"{}\" away and restart this program".format(
        cacheFolder
      )
    else:
      text = "Loading observatories..."
    self.loading = ttk.Label(self, text=text)
    self.loading.grid(column=1, row=1, padx=padding * 3, pady=padding * 3)
    ensureOnScreen(self.master)

  def loaded(self, event):
    """
    Called, once the window is shown. Flushes any queued drawing and
    loads the observatories.
    """
    self.update_idletasks()
    if not cacheFolderNotFolder:
      self.loadObservatories()

  def loadObservatories(self, reload=False):
    """
    Tries to read the cached observatories, otherwise loads them from cdas
    and schedules self.loadObservatoriesCheckDone to be run.

    Parameters
    ----------
    reload : Boolean, optional
        If True, redownloads the observatories and overrites the cache.
        The default is False.
    """
    self.observatoryGroups = None

    def done(fromCache, value):
      self.observatoryGroups = value
      if fromCache:
        self.loadObservatoriesCheckDone()

    def beforeRequest():
      if self.fObservatoryGroups is not None:
        self.tvObservatoryGroups.delete(
          *self.tvObservatoryGroups.get_children()
        )
        self.tvObservatories.delete(*self.tvObservatories.get_children())
        if self.btnReloadObservatories is not None:
          self.btnReloadObservatories["state"] = tk.DISABLED

      self.after(requestCheckInterval, self.loadObservatoriesCheckDone)

    self.cache.get(
      [
        partial(cdas.get_observatory_groups, instrumentType=it)
        for it in instrumentTypes
      ],
      done,
      onError=lambda: done(False, False),
      beforeRequest=beforeRequest,
      processResponse=lambda x: reduce(lambda a, b: intersection(a, b), x),
      reload=reload
    )

  def loadObservatoriesCheckDone(self):
    """
    Schedules itself until the download started with
    self.loadObservatories has finished, then fills the widgets.
    """
    if self.observatoryGroups is None:
      self.after(requestCheckInterval, self.loadObservatoriesCheckDone)
    else:
      if self.observatoryGroups is False:
        self.loading["text"] = """Could not load observatories.
Please check your internet connection, restart the program or try again later.
If this error persists, please check for a new version of this program or contact the developer."""

        self.loading["foreground"] = "red"
        self.loading.grid(
          column=1, row=1, padx=padding * 3, pady=padding * 2, sticky="w"
        )
        return

      if self.fObservatoryGroups is None:
        self.createObservatoryWidgets()
      self.btnReloadObservatories["state"] = tk.NORMAL
      selectGroup = None
      for obs in self.observatoryGroups:
        if obs["Name"] == "(null)":
          continue
        newItem = self.tvObservatoryGroups.insert(
          "",
          tk.END,
          text=obs["Name"],
          values=(", ".join(obs["ObservatoryId"]), )
        )
        if self.state.observatory in obs["ObservatoryId"]:
          selectGroup = newItem
      if selectGroup:
        self.tvObservatoryGroups.selection("set", selectGroup)
        self.tvObservatoryGroups.see(selectGroup)

  def createObservatoryWidgets(self):
    """
    Creates the widgets for the observatories and date selection.
    """
    self.loading.grid_forget()

    self.fObservatoriesAndDate = tk.Frame(self)
    self.fObservatoriesAndDate.grid(
      column=1, row=2, padx=padding * 2, pady=padding
    )

    # ObservatoryGroups
    (
      self.fObservatoryGroups,
      self.tvObservatoryGroups,
      self.btnReloadObservatories
    ) = scrollableTreeview(
      self.fObservatoriesAndDate,
      title="Select an observatory group " + "(all providing magnetic field, "
      + "plasma and solar wind data)",
      button="Reload"
    )
    self.tvObservatoryGroups["columns"] = ("#1", )
    self.tvObservatoryGroups.column("#0", width=10, minwidth=110, stretch=True)
    self.tvObservatoryGroups.column("#1", width=300, minwidth=30, stretch=True)
    self.tvObservatoryGroups.heading("#0", text="Observatory Group")
    self.tvObservatoryGroups.heading("#1", text="Included Observatories")
    self.btnReloadObservatories["command"
                                ] = lambda: self.loadObservatories(reload=True)
    self.fObservatoryGroups.pack(
      side="left", expand=True, fill="both", padx=padding, pady=padding
    )
    self.tvObservatoryGroups.bind(
      "<<TreeviewSelect>>", self.observatoryGroupSelected
    )

    # Observatories
    (self.fObservatories, self.tvObservatories) = scrollableTreeview(
      self.fObservatoriesAndDate,
      title="Select an observatory from the selected group"
    )
    self.tvObservatories.column("#0", width=10, minwidth=110, stretch=True)
    self.tvObservatories.configure(show="tree", height=23)
    self.fObservatories.pack(
      side="left", expand=True, fill="both", padx=padding, pady=padding
    )

    # =========================================
    # Date & Time
    # start date
    self.update_idletasks()    # update all "out-of-date" widgets
    self.fDates = tk.Frame(
      self.fObservatoriesAndDate, height=self.fObservatoryGroups.winfo_height()
    )
    self.fDates.pack(
      side="top", padx=padding, pady=padding, expand=True, fill="y"
    )

    self.cbStartDayVar = tk.IntVar(value=1)
    self.startDayVar = tk.StringVar()
    self.startDayParsed = None
    validatorDay = (
      self.register(self.validateDay), "%S", "%V", "%P", "%d", "%W"
    )
    invalidDay = (self.register(self.invalidDay), "%V", "%W")

    (
      self.cbStartDay,
      self.entryStartDay,
      self.labelStartDayHintCaption,
      self.labelStartDayHintValue
    ) = self.createEntryWithCheckbutton(
      self.fDates,
      self.cbStartDayVar,
      "Start date (format: YYYY-MM-DD[ HH[:mm[:ss]]] or Julian Day)",
      "startDay",
      self.startDayVar,
      validatorDay,
      invalidDay,
      "Please enter a date"
    )

    # =========================================
    # duration
    self.cbDurationVar = tk.IntVar(value=0)
    self.durationVar = tk.StringVar()
    self.durationParsed = TimeDelta(0, format="sec")
    validatorDuration = self.register(self.validateDuration)
    invalidDuration = self.register(self.invalidDuration)

    (self.cbDuration, self.entryDuration, self.labelDurationHint,
     _) = self.createEntryWithCheckbutton(
       self.fDates,
       self.cbDurationVar,
       "Duration (append numbers with d, h, m, s; e.g. 1d 18h)",
       "duration",
       self.durationVar, (validatorDuration, "%S", "%V", "%P", "%d"),
       (invalidDuration, "%V"),
       "Please enter a duration"
     )

    # =========================================
    # end date
    self.cbEndDayVar = tk.IntVar(value=1)
    self.endDayVar = tk.StringVar()
    self.endDayParsed = None

    (
      self.cbEndDay,
      self.entryEndDay,
      self.labelEndDayHintCaption,
      self.labelEndDayHintValue
    ) = self.createEntryWithCheckbutton(
      self.fDates,
      self.cbEndDayVar,
      "End date (same format as start date)",
      "endDay",
      self.endDayVar,
      validatorDay,
      invalidDay,
      "Please enter a date"
    )

    self.inputSelectionChanged("")

    # =========================================
    self.btnOK = ttk.Button(
      self.fDates, text="Continue", command=self.observatoryDateSelectDone
    )
    self.btnOK.pack(
      side="bottom", expand=False, fill="x", ipady=navigationButtonInnerPadding
    )

    self.master.update_idletasks()

    # set initial values
    res = self.state.startDate
    if res:
      self.setDayVariable(
        res, self.startDayVar, res.format if isinstance(res, Time) else res
      )
      self.validateDay(
        "", "focusout", self.startDayVar.get(), -1, str(self.entryStartDay)
      )

    res = self.state.endDate
    if res:
      self.setDayVariable(
        res, self.endDayVar, res.format if isinstance(res, Time) else res
      )

      self.validateDay(
        "", "focusout", self.endDayVar.get(), -1, str(self.entryEndDay)
      )

    # enable duration input & disable end date input
    self.cbDurationVar.set(1)
    self.cbEndDayVar.set(0)

    self.inputSelectionChanged("")
    ensureOnScreen(self.master)

  def createEntryWithCheckbutton(
    self,
    master,
    cbVar,
    label,
    cbCommandArg,
    entryVar,
    validator,
    invalid,
    hintText
  ):
    """
    Creates a checkbutton, entry and label and packs them

    Parameters
    ----------
    master : tk.Frame
        The master of the created widgets.

    cbVar : tk.IntVar
        Variable for the checkbutton.

    label : string
        Description for the entry, which is the text of the
        checkbutton.

    cbCommandArg : string
        Argument for the checkbutton command.

    entryVar : tk.StringVar
        Textvariable of the entry.

    validator : tuple
        The registered function for the entry validation together with its
        expected arguments.

    invalid : tuple
        Same as validator, but for invalidcommand.

    hintText : string
        The initial text in the hint label.

    Returns
    -------
    cb : ttk.Checkbutton

    entry : ttk.Entry

    hint : tk.Label

    """
    padder = tk.Label(master, text=" ")
    cb = ttk.Checkbutton(
      master,
      text=label,
      command=lambda: self.inputSelectionChanged(cbCommandArg),
      offvalue=0,
      onvalue=1,
      variable=cbVar
    )
    entry = ttk.Entry(
      master,
      textvariable=entryVar,
      validate="all",
      validatecommand=validator,
      invalidcommand=invalid
    )
    frameHints = tk.Frame(master)
    hint1 = tk.Label(frameHints, text=hintText, justify="right")
    hint2 = tk.Label(frameHints, text="", justify="left")

    padder.pack(side="top")
    cb.pack(side="top", anchor="w")
    entry.pack(side="top", fill="x")
    frameHints.pack(side="top", anchor="w")
    hint1.pack(side="left", anchor="w")
    hint2.pack(side="left", anchor="w")

    return cb, entry, hint1, hint2

  def observatoryGroupSelected(self, event):
    """
    Event handler when an observatory group was selected to fill the second
    TreeView with the observatories from the selected group.
    """
    index = self.tvObservatoryGroups.index(
      self.tvObservatoryGroups.selection()[0]
    )
    self.tvObservatories.delete(*self.tvObservatories.get_children())
    selectItem = None
    for id in self.observatoryGroups[index]["ObservatoryId"]:
      newItem = self.tvObservatories.insert("", tk.END, text=id)
      if self.state.observatory == id:
        selectItem = newItem
    if selectItem:
      self.tvObservatories.selection("set", selectItem)

  def validateDay(
    self, strInserted, validationType, newValue, insertionMode, widget
  ):
    """
    Validate function for self.entryStartDate (& EndDate). Prohibits
    anything except digits, -, ., :, and " " from being entered and
    validates the date on focusout.
    """

    if insertionMode == 0:
      return True

    if (validationType == "key"
        and re.fullmatch(r"[\d :.-]+", strInserted) is None):
      return False

    match = re.fullmatch(
      r"^(\d{4}-\d\d-\d\d)(?: (\d\d)([:. -]?\d\d)?([:. -]?\d\d)?)?$|^\d{7,}(\.\d+)?$",
      newValue.strip()
    )
    if match is None:
      if validationType == "key":
        self.invalidDay("", widget)
        return True
      return False

    try:
      if "-" in newValue:
        # normal date
        groups = list(match.group(1, 2, 3, 4))
        groups = list(
          map(
            lambda g: "00" if g is None else (g[1:] if len(g) == 3 else g),
            groups
          )
        )
        time = Time("{} {}:{}:{}".format(*groups), format="iso")
      else:
        # julian date
        time = Time(newValue, format="jd")
        time.format = "iso"

      fg = "SystemButtonText"
      caption = "Parsed ISO:\nJD:"
      value = "{}\n{:,}".format(time.iso[:-4], time.jd)
      if widget == str(self.entryStartDay):
        self.labelStartDayHintCaption["fg"] = fg
        self.labelStartDayHintCaption["text"] = caption
        self.labelStartDayHintValue["text"] = value
        self.startDayParsed = time
      else:
        self.labelEndDayHintCaption["fg"] = fg
        self.labelEndDayHintCaption["text"] = caption
        self.labelEndDayHintValue["text"] = value
        self.endDayParsed = time

      if ((widget == str(self.entryStartDay) and self.cbStartDayVar.get() == 1)
          or (widget == str(self.entryEndDay) and self.cbEndDayVar.get() == 1)):
        self.calcDisabledInput()

      return True
    except ValueError:
      if validationType == "key":
        self.invalidDay("", widget)
        return True
      return False

  def invalidDay(self, validationType, widget):
    """
    Called when the validation of self.entryStartDate or EndDate failed.
    """
    if validationType == "key":
      return
    fg = "red"
    text = "This date is invalid"
    if widget == str(self.entryStartDay):
      self.labelStartDayHintCaption["fg"] = fg
      self.labelStartDayHintCaption["text"] = text
      self.labelStartDayHintValue["text"] = ""
      self.startDayParsed = None
    else:
      self.labelEndDayHintCaption["fg"] = fg
      self.labelEndDayHintCaption["text"] = text
      self.labelEndDayHintValue["text"] = ""
      self.endDayParsed = None

  def validateDuration(
    self, strInserted, validationType, newValue, insertionMode
  ):
    """
    Validate function for self.entryDuration. Prohibits anything except
    digits, d, h, m, s and " " from being entered and sets the EndDate.
    """
    if (validationType == "key"
        and re.fullmatch(r"[\d dhms]+", strInserted) is None):
      return False

    newValue = newValue.strip()
    delta = 0
    parsed = []
    for k, v in {"d": 24 * 3600, "h": 3600, "m": 60, "s": 1}.items():
      match = re.search(r"(\d+)" + k, newValue)
      if match:
        delta += int(match.group(1)) * v
        parsed.append(match.group(1) + k)
    if delta == 0:
      if validationType == "key":
        self.invalidDuration("")
        return True
      return False

    self.labelDurationHint["fg"] = "SystemButtonText"
    self.labelDurationHint["text"] = "Parsed: " + " ".join(parsed)

    self.durationParsed = TimeDelta(delta, format="sec")

    if self.cbDurationVar.get() == 1:
      self.calcDisabledInput()

    return True

  def invalidDuration(self, validationType):
    """
    Called when the validation of self.entryDuration failed.
    """
    if validationType == "key":
      return
    self.labelDurationHint["fg"] = "red"
    self.labelDurationHint["text"] = "This duration is invalid"
    self.durationParsed = TimeDelta(0, format="sec")

  def inputSelectionChanged(self, widget):
    """
    Sets which entry is enabled to compute the other.
    """
    if widget == "startDay":
      if self.cbStartDayVar.get() == 1:
        self.cbEndDayVar.set(0)
      elif self.cbDurationVar.get() == 1:
        self.cbEndDayVar.set(1)
      else:
        self.cbDurationVar.set(1)
    elif widget == "duration":
      if self.cbDurationVar.get() == 1:
        self.cbEndDayVar.set(0)
      elif self.cbStartDayVar.get() == 1:
        self.cbEndDayVar.set(1)
      else:
        self.cbStartDayVar.set(1)
    elif widget == "endDay":
      if self.cbEndDayVar.get() == 1:
        self.cbDurationVar.set(0)
      elif self.cbStartDayVar.get() == 1:
        self.cbDurationVar.set(1)
      else:
        self.cbStartDayVar.set(1)

    self.entryStartDay["state"] = (
      tk.NORMAL if self.cbStartDayVar.get() == 1 else tk.DISABLED
    )
    self.entryDuration["state"] = (
      tk.NORMAL if self.cbDurationVar.get() == 1 else tk.DISABLED
    )
    self.entryEndDay["state"] = (
      tk.NORMAL if self.cbEndDayVar.get() == 1 else tk.DISABLED
    )

  def setDayVariable(self, parsed, variable, format):
    variable.set((parsed.iso[:-4] if format == "iso" else parsed.jd
                  ) if isinstance(parsed, Time) else parsed)

  def calcDisabledInput(self):
    """
    Calculate the third value for which its entry is disabled.
    """
    if self.cbStartDayVar.get() == 0 and self.endDayParsed:
      res = self.endDayParsed - self.durationParsed
      self.startDayParsed = res
      self.setDayVariable(res, self.startDayVar, self.endDayParsed.format)
      self.validateDay(
        "", "focusout", self.startDayVar.get(), -1, str(self.entryStartDay)
      )
    elif (self.cbDurationVar.get() == 0 and self.startDayParsed
          and self.endDayParsed):
      res = self.endDayParsed - self.startDayParsed
      self.durationParsed = res
      s = round(res.sec)
      m = s // 60
      h = m // 60
      d = h // 24
      s %= 60
      m %= 60
      h %= 24
      res = []
      if d > 0:
        res.append("{:d}d".format(int(d)))
      if h > 0:
        res.append("{:d}h".format(int(h)))
      if m > 0:
        res.append("{:d}m".format(int(m)))
      if s > 0:
        res.append("{:d}s".format(int(s)))
      self.durationVar.set(" ".join(res))
      self.validateDuration("", "focusout", self.durationVar.get(), -1)
    elif self.cbEndDayVar.get() == 0 and self.startDayParsed:
      res = self.startDayParsed + self.durationParsed
      self.endDayParsed = res
      self.setDayVariable(res, self.endDayVar, self.startDayParsed.format)
      self.validateDay(
        "", "focusout", self.endDayVar.get(), -1, str(self.entryEndDay)
      )

  def observatoryDateSelectDone(self):
    observatory = self.tvObservatories.selection()

    missingInputs = []
    if len(observatory) < 1:
      missingInputs.append("Observatory")
    if self.startDayParsed is None:
      missingInputs.append("Start date")
    if self.durationParsed.sec < 1:
      missingInputs.append("Duration")
    if self.endDayParsed is None:
      missingInputs.append("End date")

    if len(missingInputs) > 0:
      messagebox.showerror(
        title="Missing input",
        message="The following fields are missing:\n\n"
        + "\n".join(missingInputs)
      )
      return

    res = self.buildState()
    self.pageHandler("forward", res)

  def buildState(self):
    observatory = self.tvObservatories.selection()
    observatory = self.tvObservatories.item(observatory, option="text")

    res = State()
    res.observatory = observatory
    res.startDate = self.startDayParsed
    res.endDate = self.endDayParsed
    return res

  @staticmethod
  def stateSufficient(state: State):
    return True
