import tkinter as tk
# from https://stackoverflow.com/a/65524559


class ToolTip:
  def __init__(self, widget, **kwargs):
    def on_enter(event):
      self.tooltip = tk.Toplevel()
      # Leaves only the label and removes the app window
      self.tooltip.overrideredirect(True)
      self.tooltip.geometry(f'+{event.x_root+15}+{event.y_root+10}')

      tk.Label(
        self.tooltip,
        justify='left',
        background="#ffffff",
        relief='solid',
        borderwidth=1,
        **kwargs
      ).pack(ipadx=2)

    def on_leave(event):
      self.tooltip.destroy()

    widget.bind('<Enter>', on_enter)
    widget.bind('<Leave>', on_leave)
