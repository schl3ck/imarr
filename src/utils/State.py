from typing import List, Any, Dict, NamedTuple, Type, Union, Callable
from astropy.time import Time
from tkinter import Frame, Toplevel
from tkinter.messagebox import showwarning
import os.path as path
from cdflib import cdfastropy
from cdflib.cdfread import CDF
import numpy as np

from src.utils.importAllModels import importAllModels
from src.utils.utils import setFillValuesToNan


class Model:
  requiredVariables = [""]
  name = ""
  hasSettings = False

  def showSettings(self, window: Toplevel):
    pass

  def run(
    self,
    variables: "State",
    tkFrame: Frame,
    statusCallback: Callable[[float, str], None],
    doneCallback: Callable[[None], None],
    errorCallback: Callable[[str], None]
  ):
    pass

  def cancel(self):
    pass

  def showResult(self, window: Toplevel):
    pass


class StateDataset:
  id: str = None
  label: str = None

  def __init__(self, id: str, label: str):
    self.id = id
    self.label = label

  def to_dict(self):
    return {"id": self.id, "label": self.label}

  def __repr__(self):
    return str(self.to_dict())

  def __eq__(self, other: "StateDataset"):
    return (
      isinstance(other, StateDataset) and self.id == other.id
      and self.label == other.label
    )

  def copy(self) -> "StateDataset":
    s = StateDataset(self.id, self.label)
    return s


class StateSelectedVar:
  dataset: str = None
  variable: str = None
  # One of "x", "y", "z", "vector", "total" or None
  Bfield: str = None

  def __init__(self, dataset: str, variable: str, Bfield: str = None):
    """Parameters:
    dataset: ID of dataset
    variable: Name of variable in the dataset
    Bdir: one of "x", "y", "z", "total", if it is the magnetic field
    """
    self.dataset = dataset
    self.variable = variable
    self.Bfield = Bfield

  def to_dict(self):
    return {
      "dataset": self.dataset, "variable": self.variable, "Bfield": self.Bfield
    }

  def representsSameVariable(self, other: "StateSelectedVar"):
    return (
      isinstance(other, StateSelectedVar) and self.dataset == other.dataset
      and self.variable == other.variable
    )

  def __repr__(self):
    return str(self.to_dict())

  def __eq__(self, other: "StateSelectedVar"):
    return (
      isinstance(other, StateSelectedVar) and self.dataset == other.dataset
      and self.variable == other.variable and self.Bfield == other.Bfield
    )


class FoundSelectedVar(NamedTuple):
  key: str
  index: int
  var: StateSelectedVar


class StateSelectedVars:
  keys = [
    "Magnetic Field",
    "Plasma Beta",
    "Plasma Pressure",
    "Particle Density",
    "Particle Speed",
    "Temperature"
  ]
  Magnetic_Field: List[StateSelectedVar] = None
  Plasma_Beta: List[StateSelectedVar] = None
  Plasma_Pressure: List[StateSelectedVar] = None
  Particle_Density: List[StateSelectedVar] = None
  Particle_Speed: List[StateSelectedVar] = None
  Temperature: List[StateSelectedVar] = None

  def __init__(
    self,
    variables: Dict[str, List[Union[StateSelectedVar, Dict[str, str]]]] = None
  ):
    try:
      for key, value in variables.items():
        if value is not None:
          self[key] = [
            StateSelectedVar(
              i["dataset"],
              i["variable"],
              i["Bfield"] if "Bfield" in i else None
            ) if isinstance(i, dict) else
            (i if isinstance(i, StateSelectedVar) else None) for i in value
          ]
    except AttributeError:
      pass

  def __getitem__(self, key) -> List[StateSelectedVar]:
    if not isinstance(key, str) or key.replace("_", " ") not in self.keys:
      raise KeyError(key)
    return getattr(self, key.replace(" ", "_"))

  def __setitem__(self, key: str, value: List[StateSelectedVar]):
    if not isinstance(key, str) or key.replace("_", " ") not in self.keys:
      raise KeyError(key)
    setattr(self, key.replace(" ", "_"), value)

  def to_dict(self, recursive=False):
    return {
      key: [i.to_dict()
            for i in self[key]] if self[key] and recursive else self[key]
      for key in self.keys
    }

  def find(self, datasetId: str, variableName: str) -> FoundSelectedVar:
    for key in self.keys:
      if self[key] is not None:
        for i, var in enumerate(self[key]):
          if var.dataset == datasetId and var.variable == variableName:
            return FoundSelectedVar(key, i, var)
    return None

  def __repr__(self):
    return str(self.to_dict())

  def values(self):
    return (self[key] for key in self.keys if self[key])

  def items(self):
    return ((key, self[key]) for key in self.keys if self[key])

  def __eq__(self, other: "StateSelectedVars"):
    return (
      isinstance(other, StateSelectedVars)
      and all(self[key] == other[key] for key in self.keys)
    )

  def copy(self) -> "StateSelectedVars":
    s = StateSelectedVars()
    for key in self.keys:
      # yapf: disable
      s[key] = (
        [StateSelectedVar(i.dataset, i.variable, i.Bfield) for i in self[key]]
        if self[key] else None
      )
      # yapf: enable
    return s

  def has(self, key: str):
    try:
      val = self[key]
    except KeyError:
      return False
    return val is not None and len(val) > 0


class State:
  observatory: str = None
  startDate: Time = None
  endDate: Time = None
  datasets: List[StateDataset] = None
  selectedVars: StateSelectedVars = None
  selectionStart: Time = None
  selectionEnd: Time = None
  # dataset id is the key of the dict
  datasetCDFInstances: Dict[str, CDF] = None
  models: List[Type[Model]] = None

  def __init__(
    self, initialValues: Dict[str, Any] = None, ignoreErrors: bool = True
  ):
    def hasKeyOfType(key: str, t: Type, d: dict = initialValues):
      if key not in d:
        return False
      if d[key] is t or isinstance(d[key], t):
        return True
      if d[key] is None:
        return False
      return None

    def errMessage(key: str, expectedToBe: str = "", message: str = None):
      return (
        f"\"{key}\": expected to be {expectedToBe}"
        if message is None else f"\"{key}\": {message}"
      )

    if isinstance(initialValues, dict):
      errs = []
      hasKey = hasKeyOfType("observatory", str)
      if hasKey:
        self.observatory = initialValues["observatory"]
      elif hasKey is None:
        errs.append(errMessage("observatory", "of type string"))

      hasKey = hasKeyOfType("startDate", str)
      if hasKey:
        try:
          self.startDate = Time(initialValues["startDate"], format="iso")
        except ValueError:
          errs.append(errMessage("startDate", "an ISO date string"))
      elif hasKey is None:
        errs.append(errMessage("startDate", "an ISO date string"))

      hasKey = hasKeyOfType("endDate", str)
      if hasKey:
        try:
          self.endDate = Time(initialValues["endDate"], format="iso")
        except ValueError:
          errs.append(errMessage("endDate", "an ISO date string"))
      elif hasKey is None:
        errs.append(errMessage("endDate", "an ISO date string"))

      hasKey = hasKeyOfType("datasets", list)
      # yapf: disable
      if hasKey:
        if all(
          hasKeyOfType("id", str, i)
          and hasKeyOfType("label", str, i)
          for i in initialValues["datasets"]
        ):
          # yapf: enable
          self.datasets = [
            StateDataset(i["id"], i["label"]) for i in initialValues["datasets"]
          ]
        else:
          errs.append(
            errMessage(
              "datasets",
              "an array of objects with keys in [id, label] and values of type string"
            )
          )
      elif hasKey is None:
        errs.append(
          errMessage(
            "datasets",
            "an array of objects with keys in [id, label] and values of type string"
          )
        )

      hasKey = hasKeyOfType("selectedVars", dict)
      # yapf: disable
      if hasKey:
        if all(
          key.replace("_", " ") in StateSelectedVars.keys
          and (
            isinstance(val, list)
            and all(
              isinstance(i, dict)
              and hasKeyOfType("dataset", str, i)
              and hasKeyOfType("variable", str, i)
              for i in val
            )
            if val is not None else True
          )
          for (key, val) in initialValues["selectedVars"].items()
        ):
          # yapf: enable
          self.selectedVars = StateSelectedVars(initialValues["selectedVars"])
        else:
          errs.append(
            errMessage(
              "selectedVars",
              "an object with keys in [" + ', '.join(StateSelectedVars.keys)
              + "] and values of type null or an array containing objects with"
              " keys in [dataset, varaible, Bfield] and values of type string"
            )
          )
      elif hasKey is None:
        errs.append(
          errMessage(
            "selectedVars",
            "an object with keys in [" + ', '.join(StateSelectedVars.keys)
            + "] and values of type null or an array containing objects with"
            " keys in [dataset, varaible, Bfield] and values of type string"
          )
        )

      hasKey = hasKeyOfType("selectionStart", str)
      if hasKey:
        try:
          self.selectionStart = Time(
            initialValues["selectionStart"], format="iso"
          )
        except ValueError:
          errs.append(errMessage("selectionStart", "an ISO date string"))
      elif hasKey is None:
        errs.append(errMessage("selectionStart", "an ISO date string"))

      hasKey = hasKeyOfType("selectionEnd", str)
      if hasKey:
        try:
          self.selectionEnd = Time(initialValues["selectionEnd"], format="iso")
        except ValueError:
          errs.append(errMessage("selectionEnd", "an ISO date string"))
      elif hasKey is None:
        errs.append(errMessage("selectionEnd", "an ISO date string"))

      hasKey = hasKeyOfType("datasetCDFInstances", dict)
      # yapf: disable
      if hasKey:
        if all(
          (any(
            key == dataset.id
            for dataset in self.datasets
          ) if self.datasets is not None else True)
          and isinstance(val, str)
          for (key, val) in initialValues["datasetCDFInstances"].items()
        ):
          # yapf: enable
          self.datasetCDFInstances = {
            key: CDF(val)
            for (key, val) in initialValues["datasetCDFInstances"].items()
            if path.exists(val)
          }
          missing = {
            key: val
            for (key, val) in initialValues["datasetCDFInstances"].items()
            if not path.exists(val)
          }
          if len(missing):
            errs.append(
              errMessage(
                "datasetCDFInstances",
                message="missing files: \n  {}".format(
                  "\n  ".join(
                    f"{key}: {val}" for (key, val) in missing.items()
                  )
                )
              )
            )
        else:
          errs.append(
            errMessage(
              "datasetCDFInstances",
              "an object with observatory ids as keys and paths to files as values"
            )
          )

      hasKey = hasKeyOfType("models", list)
      if hasKey:
        if all(isinstance(i, str) for i in initialValues["models"]):
          imported = importAllModels()
          models = [
            next(((modelName, model)
                  for model in imported
                  if model.name == modelName), (modelName, None))
            for modelName in initialValues["models"]
          ]
          self.models = [model for name, model in models if model is not None]
          missing = [f"\"{name}\"" for name, model in models if model is None]
          if len(missing) > 0:
            errs.append(
              errMessage(
                "models", message=f"unknown model(s) {', '.join(missing)}"
              )
            )
        else:
          errs.append(
            errMessage("models", "an array of model names as strings")
          )
      elif hasKey is None:
        errs.append(errMessage("models", "an array of model names as strings"))

      if not ignoreErrors and len(errs) > 0:
        showwarning(
          "Loading session",
          "There were some problems while loading the session:\n\n"
          + "\n".join(errs) + "\n\nThe corresponding values were ignored"
        )

  def __repr__(self):
    return str(self.to_dict())

  def to_dict(self, recursive=False):
    # yapf: disable
    return {
      "observatory":
        self.observatory,
      "startDate":
        self.startDate.value if self.startDate else None,
      "endDate":
        self.endDate.value if self.endDate else None,
      "datasets":
        [i.to_dict() for i in self.datasets]
        if recursive and self.datasets else self.datasets,
      "selectedVars":
        self.selectedVars.to_dict(recursive)
        if recursive and self.selectedVars else self.selectedVars,
      "selectionStart":
        self.selectionStart.value if self.selectionStart else None,
      "selectionEnd":
        self.selectionEnd.value if self.selectionEnd else None,
      "datasetCDFInstances":
        # yapf: disable
        dict(
          (
            (
              key,
              str(
                val.file.as_posix()
                if val.compressed_file is None
                else val.compressed_file.as_posix()
              )
            )
            for (key, val) in self.datasetCDFInstances.items()
          ) if self.datasetCDFInstances is not None else dict()
        ),
        # yapf: enable
      "models":
        [model.name for model in self.models] if self.models is not None else []
    }
    # yapf: enable

  def __eq__(self, other: "State"):
    # yapf: disable
    return (
      isinstance(other, State) and all((
        len(getattr(self, i)) == len(getattr(other, i))
        and all(s == o for s, o in zip(getattr(self, i), getattr(other, i)))
        if isinstance(getattr(self, i), list)
        else getattr(self, i) == getattr(other, i)
      ) for i in State.keys())
    )

  def includes(self, other: "State"):
    if not isinstance(other, State):
      raise TypeError(
        "other has to be of type State but is of type {}".format(type(other))
      )

    for key in State.keys():
      s = getattr(self, key)
      o = getattr(other, key)
      if s is None and o is None:
        continue
      if s is None:
        # other has more contents
        return False
      if o is None:
        continue

      if s == o:
        continue
      if isinstance(s, list):
        if not isinstance(o, list):
          continue
        if len(s) != len(o):
          return False
        if all(i in s for i in o):
          continue
      return False

    return True

  def copy(self) -> "State":
    s = State()
    for key in State.keys():
      value = getattr(self, key)
      if isinstance(value, list):
        setattr(s, key, [(i.copy() if hasattr(i, "copy") else i) for i in value])
      elif value is not None:
        setattr(s, key, value.copy() if hasattr(value, "copy") else value)
    return s

  def has(self, key: str) -> bool:
    if key not in State.keys():
      return False
    t = self.__annotations__[key]
    name = getattr(t, "_name", None)
    if name == "List": t = list
    elif name == "Dict": t = dict
    return (
      isinstance(getattr(self, key), t)
      and (len(getattr(self, key)) > 0 if t == list or t == dict else True)
    )

  def closeCDFFiles(self):
    if not self.datasetCDFInstances or len(self.datasetCDFInstances) == 0:
      return
    for cdf in self.datasetCDFInstances.values():
      cdf.close()
    self.datasetCDFInstances = None

  def getData(self, dataType: str, dir: str = None, includeDate: bool = False):
    """
    Return the data for the direction dir.
    Returns (data: np.ndarray, date: astropy.time.Time) as a tuple if
    includeDate is True else only data
    """
    if self.selectedVars is None:
      raise ValueError("No variables were selected")
    acceptedDataTypes = {
      "mag": "Magnetic Field",
      "beta": "Plasma Beta",
      "pressure": "Plasma Pressure",
      "density": "Particle Density",
      "speed": "Particle Speed",
      "temperature": "Temperature"
    }
    if dataType not in acceptedDataTypes:
      raise ValueError(f"The accepted dataTypes are [{', '.join(acceptedDataTypes)}], but got {dataType}")
    if self.datasetCDFInstances is None:
      raise ValueError("No CDF files loaded")
    if dataType == "mag" and dir not in ["x", "y", "z", "total"]:
      raise ValueError("Only \"x\", \"y\", \"z\" and \"total\" is accepted as dir, at least one is required when retrieving the magnetic field")

    selectedVar = self.selectedVars[acceptedDataTypes[dataType]]
    if selectedVar is None or len(selectedVar) == 0:
      raise ValueError(f"No {acceptedDataTypes[dataType].lower()} selected")

    if dataType == "mag":
      var = next(
        (var for var in self.selectedVars.Magnetic_Field if var.Bfield == dir),
        None
      )
      if var is None:
        var = next(
          (var for var in self.selectedVars.Magnetic_Field if var.Bfield == "vector"),
          None
        )
        try:
          component = ["x", "y", "z"].index(dir)
        except ValueError:
          # dir is "total"
          return None
    else:
      var = selectedVar[0]

    if var is None:
      return None

    if var.dataset not in self.datasetCDFInstances:
      raise ValueError("CDF file for magnetic field not loaded")

    cdf = self.datasetCDFInstances[var.dataset]
    data = np.array(cdf.varget(var.variable))
    attrs = cdf.varattsget(var.variable)
    setFillValuesToNan(data, attrs)
    xDataAstropy = cdfastropy.convert_to_astropy(cdf.varget(attrs["DEPEND_0"] or "epoch"))
    xData = np.array(xDataAstropy.datetime)
    selector = self.selectionStart.datetime <= xData
    data: np.ndarray = data[selector]
    xDataAstropy: Time = xDataAstropy[selector]
    xData: np.ndarray = xData[selector]
    selector = xData <= self.selectionEnd.datetime
    data: np.ndarray = data[selector]
    xDataAstropy: Time = xDataAstropy[selector]
    xData: np.ndarray = xData[selector]
    if len(data.shape) > 1 and data.shape[1] > 1 and isinstance(component, int):
      data = data[:, component]
    return (data, xDataAstropy) if includeDate else data

  @staticmethod
  def keys():
    return [
      "observatory",
      "startDate",
      "endDate",
      "datasets",
      "selectedVars",
      "selectionStart",
      "selectionEnd",
      "datasetCDFInstances",
      "models"
    ]
