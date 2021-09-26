from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backend_bases import MouseButton, MouseEvent
from matplotlib.transforms import Bbox
from typing import List, Tuple, Callable, Union
from datetime import datetime, timezone
from astropy.time import Time

from src.utils.constants import minDragDistanceForDraggingInPlot

# adapted from https://matplotlib.org/stable/gallery/misc/cursor_demo.html#faster-redrawing-using-blitting


class PlotRangeSelection:
  """
  A start and end selection with a cursor line using blitting for faster
  redraw than replotting everything.
  """
  def __init__(
    self,
    axs: List[Axes],
    canvas: FigureCanvasTkAgg,
    bounds: Tuple[datetime, datetime],
    enabled: bool = True,
  ):
    self.axs = axs
    self.canvas = canvas
    self.background = None
    self.startLines = [self.createVline(ax, bounds, True) for ax in axs]
    self.endLines = [self.createVline(ax, bounds, True) for ax in axs]
    self.cursorLines = [self.createVline(ax, bounds, False) for ax in axs]
    self.enabled = True
    self.dragging = False
    # only x coordinate in pixels
    self.dragStartPos = None
    self.startVisible = False
    self.endVisible = False

    self._creatingBackground = False
    self._lockLines = False

    self.onSelection: List[Callable[[datetime, datetime, bool], None]] = []

    self.canvas.mpl_connect("draw_event", self.onDraw)
    self.canvas.mpl_connect("motion_notify_event", self.onMouseMove)
    self.canvas.mpl_connect("button_press_event", self.onMouseDown)
    self.canvas.mpl_connect("button_release_event", self.onMouseUp)
    self.canvas.mpl_connect("figure_leave_event", self.onFigureLeave)

  def createVline(
    self, ax: Axes, bounds: Tuple[datetime, datetime], isSelection: bool
  ):
    vline = ax.axvline(
      x=bounds[0],
      color="b" if isSelection else "r",
      lw=1,
      ls="-" if isSelection else "--"
    )
    vline.set_visible(False)
    return vline

  def onDraw(self, event):
    self.createNewBackground()

  def setSelectionVisible(
    self, startVisible=None, endVisible=None, cursorVisible=None
  ):
    needRedraw = False

    def setLines(visible, lines):
      needRedraw = False
      if visible is not None:
        needRedraw = lines[0].get_visible() != visible
        for line in lines:
          line.set_visible(visible)
      return needRedraw

    needRedraw |= setLines(startVisible, self.startLines)
    needRedraw |= setLines(endVisible, self.endLines)
    needRedraw |= setLines(cursorVisible, self.cursorLines)

    return needRedraw

  def createNewBackground(self):
    if self._creatingBackground:
      # discard calls triggered from within this function
      return
    self._creatingBackground = True
    linesVisible = self._lockLines
    self.setSelectionVisible(
      startVisible=linesVisible, endVisible=linesVisible, cursorVisible=False
    )
    self.canvas.draw()
    if not linesVisible:
      self.background = self.canvas.copy_from_bbox(self.getFullBbox())
    self.setSelectionVisible(
      startVisible=self.startVisible,
      endVisible=self.endVisible,
      cursorVisible=True
    )
    self._creatingBackground = False

  def onMouseDown(self, event: MouseEvent):
    if self.enabled is False or self._lockLines:
      return

    leftMouse = event.button == MouseButton.LEFT
    rightMouse = event.button == MouseButton.RIGHT
    if not leftMouse and not rightMouse:
      return

    if self.background is None:
      self.createNewBackground()
    if event.inaxes:
      # only enable dragging with left mouse button
      x = event.xdata
      if leftMouse:
        if minDragDistanceForDraggingInPlot == 0:
          self.dragging = True
        else:
          self.dragStartPos = event.x
        self.setSelectionVisible(startVisible=True)
        self.startVisible = True
        for line in self.startLines:
          line.set_xdata(x)

      elif rightMouse:
        self.setSelectionVisible(endVisible=True)
        self.endVisible = True
        for line in self.endLines:
          line.set_xdata(x)

      self.updateFigure()
      self.dispatchOnSelection()

  def onMouseUp(self, event: MouseEvent):
    if self.enabled is False or self._lockLines:
      return

    dragged = self.dragging
    self.dragging = False
    self.dragStartPos = None
    self.updateFigure()
    if dragged:
      self.dispatchOnSelection()

  def onMouseMove(self, event: MouseEvent):
    if self._lockLines:
      return

    if self.background is None:
      self.createNewBackground()
    if (self.dragStartPos and
        abs(self.dragStartPos - event.x) >= minDragDistanceForDraggingInPlot):
      self.dragging = True
    if self.dragging:
      self.setSelectionVisible(endVisible=True)
      self.endVisible = True

    # update the line positions
    x = event.xdata

    if self.dragging:
      for line in self.endLines:
        line.set_xdata(x)
    for line in self.cursorLines:
      line.set_xdata(x)

    self.updateFigure()

    if self.dragging:
      self.dispatchOnSelection()

  def onFigureLeave(self, event):
    if self.enabled is False or self._lockLines:
      return

    dragged = self.dragging
    self.dragging = False
    self.dragStartPos = None
    self.updateFigure()
    if dragged:
      self.dispatchOnSelection()

  def updateFigure(self):
    self.canvas.restore_region(self.background)
    for ax, start, end, cursor in zip(self.axs, self.startLines, self.endLines, self.cursorLines):
      ax.draw_artist(cursor)
      if self.startVisible:
        ax.draw_artist(start)
      if self.endVisible:
        ax.draw_artist(end)
    self.canvas.blit(self.getFullBbox())

  def getFullBbox(self):
    return Bbox.union([ax.bbox for ax in self.axs])

  def lock(self):
    if self.startVisible and self.endVisible:
      self._lockLines = True
      self.createNewBackground()

  def unlock(self):
    self._lockLines = False
    self.updateFigure()

  def dispatchOnSelection(self):
    secondsPerDay = 86400

    start = self.startLines[0].get_xdata() if self.startVisible else None
    end = self.endLines[0].get_xdata() if self.endVisible else None
    if start:
      if isinstance(start, datetime):
        start = Time(start)
      else:
        start = Time(
          datetime.fromtimestamp(start * secondsPerDay, timezone.utc)
        )
    if end:
      if isinstance(end, datetime):
        end = Time(end)
      else:
        end = Time(datetime.fromtimestamp(end * secondsPerDay, timezone.utc))
    if start and end and end < start:
      tmp = start
      start = end
      end = tmp
    for cb in self.onSelection:
      cb(start, end, self.dragging)

  def setSelection(
    self,
    start: Union[Time, datetime] = None,
    end: Union[Time, datetime] = None
  ):
    if self.background is None:
      self.createNewBackground()
    if isinstance(start, (Time, datetime)):
      time = start.datetime if isinstance(start, Time) else start
      self.setSelectionVisible(startVisible=True)
      self.startVisible = True
      for line in self.startLines:
        line.set_xdata(time)
    else:
      self.setSelectionVisible(startVisible=False)
      self.startVisible = False

    if isinstance(end, (Time, datetime)):
      time = end.datetime if isinstance(end, Time) else end
      self.setSelectionVisible(endVisible=True)
      self.endVisible = True
      for line in self.endLines:
        line.set_xdata(time)
    else:
      self.setSelectionVisible(endVisible=False)
      self.endVisible = False

    self.updateFigure()
