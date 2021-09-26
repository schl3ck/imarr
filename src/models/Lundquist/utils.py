import numpy as np


def averageB(Bx, By, Bz):
  moy = np.nanmean(np.sqrt(Bx**2 + By**2 + Bz**2))
  return moy


def create_r(n, v, R0, b, teta0, E):
  t = np.linspace(0, 10000, 10000)
  alpha = teta0 - np.arccos(b / R0) - np.pi / 2
  teta = (
    np.arctan(-v * t / b + np.tan(np.arccos(b / R0))) + teta0
    - np.arccos(b / R0)
  )
  r = R0 * (np.sin(teta0) - np.tan(alpha) * np.cos(teta0)) / (
    np.sin(teta) - np.tan(alpha) * np.cos(teta)
  )
  r = r / (R0 + E * t)
  l = np.argwhere(r[1:len(r)] >= 1)
  if len(l) == 0:
    l = len(r)
  else:
    l = l[0][0]
  r = r[0:l]
  t = np.linspace(0, l, n)

  teta = (
    np.arctan(-v * t / b + np.tan(np.arccos(b / R0))) + teta0
    - np.arccos(b / R0)
  )
  r = R0 * (np.sin(teta0) - np.tan(alpha) * np.cos(teta0)) / (
    np.sin(teta) - np.tan(alpha) * np.cos(teta)
  )
  r = r / (R0 + E * t)

  return (r, teta, t)


def rotation(Bx, By, Bz, theta, phi):
  fact = np.pi / 180
  theta = theta * fact    # Define the angles
  phi = phi * fact

  # yapf: disable
  #Rotation Matrix calculation
  D = np.array([[1, 0, 0],
                [0, np.cos(phi), np.sin(phi)],
                [0, -np.sin(phi), np.cos(phi)]])
  E = np.array([[np.cos(theta), np.sin(theta), 0],
                [-np.sin(theta), np.cos(theta), 0],
                [0, 0, 1]])
  # yapf: enable
  A = np.matmul(D, E)

  B = np.empty((len(Bx), 3, 1), dtype=Bx.dtype)
  B[:, 0, 0] = Bx
  B[:, 1, 0] = By
  B[:, 2, 0] = Bz

  Res = np.matmul(A, B)
  Bx[:] = Res[:, 0, 0]
  By[:] = Res[:, 1, 0]
  Bz[:] = Res[:, 2, 0]
  return (Bx, By, Bz)
