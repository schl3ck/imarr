import tkinter as tk

from src.utils.State import State

class BasePage(tk.Frame):
  skipOnBackward = False
  disableSaveHotkey = False

  def buildState(self) -> State:
    pass

  @staticmethod
  def stateSufficient(state: State) -> bool:
    return False
