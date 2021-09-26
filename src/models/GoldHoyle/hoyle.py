import numpy as np
from typing import Callable, List
import matplotlib.pyplot as plt
from dataclasses import dataclass
from .utils import rotation, averageB


@dataclass
class Result:
  magFieldError: float
  B0: float
  B0Error: float
  B0MinimizationArray: List[float]
  b: float
  bMinimizationArray: List[float]
  R0: float
  R0MinimizationArray: List[float]
  theta: float
  thetaMinimizationArray: List[float]
  phi: float
  phiMinimizationArray: List[float]


@dataclass
class Settings:
  nIterations: int = 10
  nPoints: int = 1000


def fitting_Hoyle(
  Bx: np.ndarray,
  By: np.ndarray,
  Bz: np.ndarray,
  Btotal: np.ndarray,
  r: np.ndarray,
  settings: Settings,
  statusCallback: Callable[[str], None],
  isCanceled: Callable[[], bool]
):
  if Btotal is None:
    Btotal = np.sqrt(Bx**2 + By**2 + Bz**2)
  minB0: float = np.nanmax(Btotal)
  minb: float = 0
  minR0: float = 5
  minTheta: float = 0.0
  minPhi: float = 0.0

  toRad = np.pi / 180

  def createStatus(iteration: int):
    # yapf: disable
    return (
      f"{iteration + 1}/{settings.nIterations}\n"
      f"B0: {minB0}\n"
      f"b: {minb}\n"
      f"R0: {minR0}\n"
      f"theta: {minTheta}\n"
      f"phi: {minPhi}"
    )
    # yapf: enable

  arrayB0 = np.empty(settings.nPoints)
  rangeB0 = np.linspace(-16, 16, settings.nPoints)
  arrayb = np.empty_like(arrayB0)
  rangeb = np.linspace(1, 15, settings.nPoints)
  arrayR0 = np.empty_like(arrayB0)
  rangeR0 = np.linspace(0.01, 50, settings.nPoints)
  arrayTheta = np.empty_like(arrayB0)
  rangeTheta = np.linspace(0, 360, settings.nPoints)
  arrayPhi = np.empty_like(arrayB0)
  rangePhi = np.linspace(0, 360, settings.nPoints)

  totalIterations = float(settings.nPoints * 5 * settings.nIterations)
  currentIterations = 0

  statusString = ""

  def status():
    progress = currentIterations / totalIterations
    statusCallback(progress, statusString)

  statusEveryIterations = settings.nPoints / 10

  for iteration in range(settings.nIterations):
    arrayB0.fill(0.)
    arrayb.fill(0.)
    arrayR0.fill(0.)
    arrayTheta.fill(0.)
    arrayPhi.fill(0.)

    statusString = f"minimizing B0 {createStatus(iteration)}"
    # Minimise B0
    for index, B0 in enumerate(rangeB0):
      if isCanceled():
        return
      currentIterations += 1
      if index % statusEveryIterations == 0:
        status()

      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = B0 / (1 + minb**2 * (r / minR0)**2)
      # Define Btheta
      Btheta = B0 * minb * r / (
        (1 + minb**2 *
         (r / minR0)**2) * (minR0 + (r / minR0) * np.cos(minTheta * toRad))
      )
      arrayB0[index] = calcAi(Bx, By, Bz, Br, Bphi, Btheta)

    minB0 = rangeB0[arrayB0.argmin()]

    statusString = f"minimizing b {createStatus(iteration)}"
    # Minimise b
    for index, b in enumerate(rangeb):
      if isCanceled():
        return
      currentIterations += 1
      if index % statusEveryIterations == 0:
        status()

      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = minB0 / (1 + b**2 * (r / minR0)**2)
      # Define Btheta
      Btheta = minB0 * b * r / (
        (1 + b**2 *
         (r / minR0)**2) * (minR0 + (r / minR0) * np.cos(minTheta * toRad))
      )
      arrayb[index] = calcAi(Bx, By, Bz, Br, Bphi, Btheta)

    minb = rangeb[arrayb.argmin()]

    statusString = f"minimizing R0 {createStatus(iteration)}"
    # Minimise R0
    for index, R0 in enumerate(rangeR0):
      if isCanceled():
        return
      currentIterations += 1
      if index % statusEveryIterations == 0:
        status()

      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = minB0 / (1 + minb**2 * (r / R0)**2)
      # Define Btheta
      Btheta = minB0 * minb * r / ((1 + minb**2 * (r / R0)**2) *
                                   (R0 + (r / R0) * np.cos(minTheta * toRad)))
      arrayR0[index] = calcAi(Bx, By, Bz, Br, Bphi, Btheta)

    minR0 = rangeR0[arrayR0.argmin()]

    statusString = f"minimizing theta {createStatus(iteration)}"
    # Minimise theta
    for index, theta in enumerate(rangeTheta):
      if isCanceled():
        return
      currentIterations += 1
      if index % statusEveryIterations == 0:
        status()

      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = minB0 / (1 + minb**2 * (r / minR0)**2)
      # Define Btheta
      Btheta = minB0 * minb * r / (
        (1 + minb**2 *
         (r / minR0)**2) * (minR0 + (r / minR0) * np.cos(theta * toRad))
      )
      # Rotate the frame with theta and phi
      Br, Bphi, Btheta = rotation(Br, Bphi, Btheta, theta, minPhi)
      arrayTheta[index] = calcAi(Bx, By, Bz, Br, Bphi, Btheta)

    minTheta = rangeTheta[arrayTheta.argmin()]

    statusString = f"minimizing phi {createStatus(iteration)}"
    # Minimise phi
    for index, phi in enumerate(rangePhi):
      if isCanceled():
        return
      currentIterations += 1
      if index % statusEveryIterations == 0:
        status()

      # Define Br
      Br = np.zeros_like(r)
      # define Bphi
      Bphi = minB0 / (1 + minb**2 * (r / minR0)**2)
      # Define Btheta
      Btheta = minB0 * minb * r / (
        (1 + minb**2 *
         (r / minR0)**2) * (minR0 + (r / minR0) * np.cos(minTheta * toRad))
      )
      # Rotate the frame with theta and phi
      Br, Bphi, Btheta = rotation(Br, Bphi, Btheta, minTheta, phi)
      arrayPhi[index] = calcAi(Bx, By, Bz, Br, Bphi, Btheta)

    minPhi = rangePhi[arrayPhi.argmin()]

  avgB = averageB(Bx, By, Bz)
  B0Error = min(arrayB0)

  return Result(
    magFieldError=100 * B0Error / avgB,
    B0=minB0,
    B0Error=B0Error,
    B0MinimizationArray=arrayB0,
    b=minb,
    bMinimizationArray=arrayb,
    R0=minR0,
    R0MinimizationArray=arrayR0,
    theta=minTheta,
    thetaMinimizationArray=arrayTheta,
    phi=minPhi,
    phiMinimizationArray=arrayPhi
  )


def calcAi(
  Bx: np.ndarray,
  By: np.ndarray,
  Bz: np.ndarray,
  Br: np.ndarray,
  Bphi: np.ndarray,
  Btheta: np.ndarray
):
  x = Bx - Br
  y = By - Bphi
  z = Bz - Btheta
  tot = (x**2 + y**2 + z**2)
  tot2 = (Bx**2 + By**2 + Bz**2)
  return np.sum(filterNaNs(tot)) / np.sum(filterNaNs(tot2))
  # return np.sqrt(
  #   np.trapz(filterNaNs(abs(x)))**2 + np.trapz(filterNaNs(abs(y)))**2
  #   + np.trapz(filterNaNs(abs(z)))**2
  # )


def filterNaNs(ar: np.ndarray):
  return ar[~np.isnan(ar)]


titleFontSize = 20
labelFontSize = 17


# Plot the color map of the magnetic field components:
def Hoyle_phi(B0, R0, b, n_points):
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points, dtype=float)
  theta = np.radians(np.arange(0, 360), dtype=float)
  r, theta = np.meshgrid(r, theta)
  Bphi = B0 / (1 + r**2 * b**2)
  fig, ax = plt.subplots(figsize=(6.5, 5), subplot_kw=dict(projection='polar'))
  pp = ax.contourf(theta, r, Bphi)    # ,levels=np.arange(-16,1,1))
  colorbar = fig.colorbar(pp, label='Magnitude [nT]')
  ax.set_title('Gold-Hoyle $B_\\phi$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig


def Hoyle_theta(B0, R0, b, n_points):
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points)
  theta = np.radians(np.arange(0, 360))
  r, theta = np.meshgrid(r, theta)
  Btheta = B0 * R0 * b * r / ((1 + b**2 * r**2) * (R0 + r * np.cos(theta)))
  fig, ax = plt.subplots(figsize=(6.5, 5), subplot_kw=dict(projection='polar'))
  pp = ax.contourf(theta, r, Btheta, levels=np.arange(-30, 1, 2))
  colorbar = fig.colorbar(pp, label='Magnitude [nT]')
  ax.set_title('Gold-Hoyle $B_\\theta$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig


def Hoyle_tot(B0, R0, b, n_points):
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points)
  theta = np.radians(np.arange(0, 360))
  r, theta = np.meshgrid(r, theta)
  Bphi = B0 / (1 + r**2 * b**2)
  Btheta = B0 * R0 * b * r / ((1 + b**2 * r**2) * (R0 + r * np.cos(theta)))
  Btot = np.sqrt(Bphi**2 + Btheta**2)
  fig, ax = plt.subplots(figsize=(6.5, 5), subplot_kw=dict(projection='polar'))
  pp = ax.contourf(theta, r, Btot)
  colorbar = fig.colorbar(pp, label='Magnitude [nT]')
  ax.set_title('Gold-Hoyle $B_\\mathrm{tot}$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig
