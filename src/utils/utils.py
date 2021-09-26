from datetime import datetime
import numpy as np
import tkinter as tk
from tkinter import ttk
import json
from typing import List, Dict, Tuple, Union
import webbrowser
import re
import platform
from astropy.time import Time



def intersection(a, b):
  """
    Get the intersection between two lists

    Parameters
    ----------
    a : list
        The first list
    b : list
        The second list
    
    Returns
    -------
    list
        The instersection between a and b
    """
  return sorted([
    json.loads(i) for i in set([json.dumps(aa) for aa in a])
    & set([json.dumps(bb) for bb in b])
  ],
                key=lambda x: x["Name"])


def scrollableTreeview(
  master: Union[tk.Frame, ttk.Frame],
  title: str = None,
  button: Union[str, List[str]] = None,
  unpackButtons: bool = False,
  noXScrollbar: bool = False
) -> Union[Tuple[ttk.Frame, ttk.Treeview],
           Tuple[ttk.Frame, ttk.Treeview, ttk.Button],
           Tuple[ttk.Frame, ttk.Treeview, List[ttk.Button]]]:
  """
  Creates a treeview and adds a scrollbar to it

  Parameters
  ----------
  master : tk.Frame, ttk.Frame
      The master which should contain the widgets
  title : str
      Adds a label describing the treeview
  button : str, list[str]
      Adds a button with this text on it
  unpackButtons : bool
      When button is a list, all the created buttons are returned as a list,
      except when this is True, then they are appended at the end of the
      returned tuple.
      Default: False
  noXScrollbar : bool
      If this is True then no horizontal scrollbar will be added. Useful when
      the treeview won't have any additional columns.
      Default: False

  Returns
  -------
  unpackButtons = True:
    ttk.Frame, ttk.Treeview, ttk.Button, ...
  unpackButtons = False:
    ttk.Frame, ttk.Treeview, [ttk.Button, ...]
      The button is only created and returned if a text is specified for it.
      If only a string was passed for "button" then it is automatically unpacked
  """
  f = ttk.Frame(master)
  scrollbarX = None if noXScrollbar else ttk.Scrollbar(f, orient=tk.HORIZONTAL)
  scrollbarY = ttk.Scrollbar(f)
  tv = ttk.Treeview(
    f, selectmode=tk.BROWSE, height=20, yscrollcommand=scrollbarY.set
  )
  if scrollbarX:
    tv["xscrollcommand"] = scrollbarX.set
    scrollbarX["command"] = tv.xview

  scrollbarY["command"] = tv.yview

  # set focus to the selected or first item when the treeview recieves focus
  def focusIn(event: tk.Event):
    widget: ttk.Treeview = event.widget
    item = next(iter(widget.selection()), None)
    fromChildren = False
    if not item:
      item = next(iter(widget.get_children()), None)
      fromChildren = True
    if item:
      widget.focus(item)
      if fromChildren:
        widget.selection_set(item)

  tv.bind("<FocusIn>", focusIn)

  label = btn = None
  if title:
    label = ttk.Label(f, text=title)
    label.grid(column=1, row=1)

  tv.grid(column=1, row=2, sticky="nsew")
  scrollbarY.grid(column=2, row=2, sticky="ns")
  if scrollbarX:
    scrollbarX.grid(column=1, row=3, sticky="we")

  res = f, tv

  if button:
    row = 4
    btns = tuple()
    wasList = True
    if not isinstance(button, list):
      wasList = False
      button = [button]
    for b in button:
      btn = ttk.Button(f, text=b)
      btn.grid(column=1, row=row, columnspan=2, sticky="we")
      row += 1
      btns += btn,
    if not wasList or unpackButtons:
      res += btns
    else:
      res += list(btns),

  return res


def scrollableListbox(
  master: Union[tk.Frame, ttk.Frame],
  title: str = None,
  button: str = None
) -> Union[Tuple[ttk.Frame, tk.Listbox],
           Tuple[ttk.Frame, tk.Listbox, ttk.Button]]:
  """
  Creates a listbox and adds a scrollbar to it

  Parameters
  ----------
  master : tk.Frame, ttk.Frame
      The master which should contain the widgets
  title : str
      Adds a label describing the treeview

  Returns
  -------
  ttk.Frame, tk.Listbox, ttk.Button
      The button is only created and returned if a text is specified for it
  """
  f = ttk.Frame(master)
  scrollbarX = ttk.Scrollbar(f, orient=tk.HORIZONTAL)
  scrollbarY = ttk.Scrollbar(f)
  lb = tk.Listbox(
    f,
    selectmode=tk.BROWSE,
    height=20,
    width=50,
    xscrollcommand=scrollbarX.set,
    yscrollcommand=scrollbarY.set
  )
  scrollbarX["command"] = lb.xview
  scrollbarY["command"] = lb.yview

  if title:
    label = ttk.Label(f, text=title)
    label.grid(column=1, row=1)

  lb.grid(column=1, row=2, sticky="news")
  scrollbarY.grid(column=2, row=2, sticky="ns")
  scrollbarX.grid(column=1, row=3, sticky="we")

  res = f, lb

  if button:
    btn = ttk.Button(f, text=button)
    btn.grid(column=1, row=4, columnspan=2, sticky="we")
    res += btn,

  return res


def titleCaseToSentence(text):
  return re.sub(r"([a-z])([A-Z])", r"\1 \2", text)


def openLink(event=None, url=None):
  if event is not None:
    url = event.widget.cget("text")
  if url is None:
    return
  webbrowser.open_new(url)


def dictToGridLabels(
  master: tk.Frame,
  content: Union[Dict, List],
  order: List = None,
  maxWidth: int = None
) -> None:
  """
  Pretty prints a dictionary or list with the keys as labels and an optional
  order of the keys
  """
  if order is None:
    if isinstance(content, dict):
      order = content.keys()
    else:
      order = content

  if isinstance(content, list) and all([type(i) is str for i in content]):
    tk.Label(master, text="\n".join(content), justify="left").grid(sticky="w")
    return

  for row, k in enumerate(order):
    childrenOrder = None
    if isinstance(content, dict):
      if isinstance(k, dict):
        childrenOrder = k["children"]
        k = k["name"]
      if k not in content:
        continue
      v = content[k]
    else:
      v = k
      k = None

    # key
    if k:
      tk.Label(
        master, text=titleCaseToSentence(k).replace("Pi", "PI") + ":"
      ).grid(
        row=row, sticky="ne"
      )
    # value
    if isinstance(v, list):
      frame = tk.Frame(master)
      frame.grid(row=row, column=1, sticky="we")
      dictToGridLabels(frame, v, maxWidth=maxWidth)
    elif isinstance(v, dict):
      frame = tk.Frame(master)
      frame.grid(row=row, column=1, sticky="we")
      dictToGridLabels(frame, v, childrenOrder, maxWidth=maxWidth)
    else:
      lbl = tk.Message(master, text=str(v))
      if str(v)[:4] == "http":
        lbl["fg"] = "blue"
        lbl["cursor"] = "hand2"
        lbl.bind("<Button-1>", openLink)
      if maxWidth:
        lbl["width"] = maxWidth
      lbl.grid(row=row, column=1, sticky="w")


def languageJoin(array, quoteItems=False):
  res = ""
  lastPos = len(array) - 1
  for i, item in enumerate(array):
    if len(res) > 0:
      res += " and " if i == lastPos else ", "
    if len(str(item)) > 0 and quoteItems:
      res += quoteItems if type(quoteItems) is str else "'"
    res += str(item)
    if len(str(item)) > 0 and quoteItems:
      res += quoteItems if type(quoteItems) is str else "'"

  return res


def pickFromDict(d: Dict, keys: List[str]):
  res = {}
  for i in keys:
    if i in d:
      res[i] = d[i]
  return res


def Time2StrCdasArgument(time: Time) -> str:
  return re.sub(r"[.:-]", r"", re.sub(r"\.000$", r"Z", time.isot))


def Time2USDateStr(dt: datetime, asDict: bool = False) -> str:
  """
  Format a datetime in the US date format like `Jan 1, 2021`
  """
  if not isinstance(dt, datetime):
    raise TypeError("Argument dt has to be of type datetime")
  year = dt.year
  month = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Oct", "Nov", "Dec"
  ][dt.month - 1]
  day = dt.day

  return {
    "month": month, "day": day, "year": year
  } if asDict else "{} {}, {}".format(month, day, year)


def TimeRange2USDateStr(startTime: datetime, endTime: datetime) -> str:
  """
  Format two datetimes in the US date format
  When the year doesn't match: `Dec 31, 2020 - Jan 1, 2021`
  When the month doesn't match: `Jan 31 - Feb 1, 2021`
  When the day doesn't match: `Jan 1 - 2, 2021`
  Otherwise it returns just the startTime: `Jan 1, 2021`
  """
  if not isinstance(startTime, datetime):
    raise TypeError("Argument startTime has to be of type datetime")
  if not isinstance(endTime, datetime):
    raise TypeError("Argument endTime has to be of type datetime")
  start = Time2USDateStr(startTime, True)
  end = Time2USDateStr(endTime, True)

  if startTime.year != endTime.year:
    return "{} - {}".format(Time2USDateStr(startTime), Time2USDateStr(endTime))
  elif startTime.month != endTime.month:
    return "{} {} - {} {}, {}".format(
      start["month"], start["day"], end["month"], end["day"], start["year"]
    )
  elif startTime.day != endTime.day:
    return "{} {} - {}, {}".format(
      start["month"], start["day"], end["day"], start["year"]
    )
  else:
    return Time2USDateStr(startTime)


def isMacOS():
  return platform.system() == "darwin"


def ensureOnScreen(root: tk.Tk):
  if str(root) != ".":
    return

  root.update_idletasks()
  geometry = root.wm_geometry()
  match = re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", geometry)
  width, height, x, y = tuple(int(i) for i in match.group(1, 2, 3, 4))
  right = x + width
  bottom = y + height
  scrWidth = root.winfo_screenwidth()
  scrHeight = root.winfo_screenheight()

  left = -1
  top = -1
  if right > scrWidth:
    left = scrWidth - width
  if bottom > scrHeight:
    top = scrHeight - height

  if left >= 0 or top >= 0:
    if left == -1:
      left = x
    if top == -1:
      top = y

    root.geometry("+{}+{}".format(left, top))


def setFillValuesToNan(data: np.ndarray, cdfAttrs: dict):
  if "FILLVAL" in cdfAttrs:
    data[data == cdfAttrs["FILLVAL"][0]] = np.nan
  if "VALIDMIN" in cdfAttrs:
    data[data < cdfAttrs["VALIDMIN"][0]] = np.nan
  if "VALIDMAX" in cdfAttrs:
    data[data > cdfAttrs["VALIDMAX"][0]] = np.nan
