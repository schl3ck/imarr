from typing import Callable, List
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from .utils import rotation, averageB


@dataclass
class Result:
  magFieldError: float
  B0: float
  B0Error: float
  B0MinimizationArray: List[float]
  theta: float
  thetaMinimizationArray: List[float]
  phi: float
  phiMinimizationArray: List[float]


@dataclass
class Settings:
  nIterations: int = 6
  nPointsB0: int = 1000
  nPointsAngles: int = 1000


def fitting_lundquist(
  Bx: np.ndarray,
  By: np.ndarray,
  Bz: np.ndarray,
  Btotal: np.ndarray,
  r: np.ndarray,
  settings: Settings,
  statusCallback: Callable[[str], None],
  isCanceled: Callable[[], bool]
):
  import scipy
  if Btotal is None:
    Btotal = np.sqrt(Bx**2 + By**2 + Bz**2)

  minB0: float = np.nanmax(Btotal)
  rangeB0 = np.linspace(0, 32, settings.nPointsB0)
  # orientation
  minTheta = 0.0
  minPhi = 0.0

  rangeTheta = np.linspace(0, 360, settings.nPointsAngles)
  rangePhi = np.linspace(0, 360, settings.nPointsAngles)
  arrayB0 = np.empty(settings.nPointsB0)
  arrayTheta = np.empty(settings.nPointsAngles)
  arrayPhi = np.empty_like(arrayTheta)

  def createStatus(iteration: int):
    # yapf: disable
    return (
      f"{iteration + 1}/{settings.nIterations}\n"
      f"B0: {minB0}\n"
      f"theta: {minTheta}\n"
      f"phi: {minPhi}"
    )
    # yapf: enable

  totalIterations = float(
    (settings.nPointsB0 + settings.nPointsAngles * 2) * settings.nIterations
  )
  currentIterations = 0

  statusString = ""

  def status():
    progress = currentIterations / totalIterations
    statusCallback(progress, statusString)

  statusEveryIterations = settings.nPointsAngles / 10

  for iteration in range(settings.nIterations):
    arrayB0.fill(0.)
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
      Bphi = B0 * scipy.special.j1(2.41 * (r))
      # Define Bz
      BzModeled = B0 * scipy.special.j0(2.41 * (r))
      # Rotate the frame with theta and phi
      Br, Bphi, BzModeled = rotation(Br, Bphi, BzModeled, minTheta, minPhi)
      arrayB0[index] = calcAi(Bx, By, Bz, Br, Bphi, BzModeled)

    minB0 = rangeB0[arrayB0.argmin()]

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
      Bphi = minB0 * scipy.special.j1(2.41 * (r))
      # Define Btheta
      BzModeled = minB0 * scipy.special.j0(2.41 * (r))
      # Rotate the frame with theta and phi
      Br, Bphi, BzModeled = rotation(Br, Bphi, BzModeled, theta, minPhi)
      arrayTheta[index] = calcAi(Bx, By, Bz, Br, Bphi, BzModeled)

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
      Bphi = minB0 * scipy.special.j1(2.41 * (r))
      # Define Btheta
      BzModeled = minB0 * scipy.special.j0(2.41 * (r))
      # Rotate the frame with theta and phi
      Br, Bphi, BzModeled = rotation(Br, Bphi, BzModeled, minTheta, phi)
      arrayPhi[index] = calcAi(Bx, By, Bz, Br, Bphi, BzModeled)

    minPhi = rangePhi[arrayPhi.argmin()]

  # calculate the average of the magnetic field within the ranges
  avgB = averageB(Bx, By, Bz)
  B0Error = min(arrayB0)

  return Result(
    magFieldError=100 * B0Error / avgB,
    B0=minB0,
    B0Error=B0Error,
    B0MinimizationArray=arrayB0,
    theta=minTheta,
    thetaMinimizationArray=arrayTheta,
    phi=minPhi,
    phiMinimizationArray=arrayPhi
  )


def calcAi(Bx, By, Bz, Br, Bphi, BzModeled):
  x = abs(Bx - Br)
  y = abs(By - Bphi)
  z = abs(Bz - BzModeled)
  # return np.sqrt(
  #   np.trapz(filterNaNs(abs(x)))**2 + np.trapz(filterNaNs(abs(y)))**2
  #   + np.trapz(filterNaNs(abs(z)))**2
  # )
  tot = (x**2 + y**2 + z**2)
  tot2 = (Bx**2 + By**2 + Bz**2)
  return np.sum(filterNaNs(tot)) / np.sum(filterNaNs(tot2))


def filterNaNs(ar: np.ndarray):
  return ar[~np.isnan(ar)]

titleFontSize = 20
labelFontSize = 17

# Plot the color map of the magnetic field components:
def Lund_Bphi(B0, n_points):
  import scipy
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points)
  theta = np.radians(np.arange(0, 360))
  r, theta = np.meshgrid(r, theta)
  Bphi = B0 * scipy.special.j1(2.41 * (r))    # define Bphi
  Bz = B0 * scipy.special.j0(2.41 * (r))    # Define Bz
  Btot = np.sqrt(Bphi**2 + Bz**2)
  fig, ax = plt.subplots(figsize=(6.5, 5), subplot_kw=dict(projection='polar'))
  pp = plt.contourf(theta, r, Bphi)
  colorbar = plt.colorbar(pp, label='Magnitude [nT]')
  plt.title('Lundquist $B_\\phi$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig


def Lund_Bz(B0, n_points):
  import scipy
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points)
  phi = np.radians(np.arange(0, 360))
  r, phi = np.meshgrid(r, phi)
  Bphi = B0 * scipy.special.j1(2.41 * (r))    # define Bphi
  Bz = B0 * scipy.special.j0(2.41 * (r))    # Define Bz
  Btot = np.sqrt(Bphi**2 + Bz**2)
  fig, ax = plt.subplots(figsize=(6.5, 5), subplot_kw=dict(projection='polar'))
  pp = plt.contourf(phi, r, Bz)
  colorbar = plt.colorbar(pp, label='Magnitude [nT]')
  plt.title('Lundquist $B_z$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig


def Lund_tot(B0, n_points):
  import scipy
  defaultFontSize = plt.rcParams["font.size"]
  plt.rcParams.update({"font.size": labelFontSize})
  r = np.linspace(0, 1, n_points)
  theta = np.radians(np.arange(0, 360))
  r, theta = np.meshgrid(r, theta)
  Bphi = B0 * scipy.special.j1(2.41 * (r))    # define Bphi
  Bz = B0 * scipy.special.j0(2.41 * (r))    # Define Bz
  Btot = np.sqrt(Bphi**2 + Bz**2)
  fig, ax = plt.subplots(subplot_kw=dict(projection='polar'))
  pp = plt.contourf(theta, r, Btot)
  colorbar = plt.colorbar(pp, label='Magnitude [nT]')
  plt.title('Lundquist $B_\\mathrm{tot}$', fontsize=titleFontSize, pad=15)
  fig.subplots_adjust(left=0.05, bottom=0.07, right=0.9, top=0.8)
  plt.rcParams.update({"font.size": defaultFontSize})
  return fig
