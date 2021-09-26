import re
import shutil
from pathlib import Path
from datetime import datetime
import cdflib
from threading import Thread
from typing import List, Callable, Any, TypeVar, Generic, Union, Dict

from .constants import requestMaxRetries, cacheFolder, cdas


def get(
  fileDescription: (
    Union[Dict[str, Union[str, int]], List[Dict[str, Union[str, int]]]]
  ),
  onDone: Callable[[bool, cdflib.cdfread.CDF], None],
  onError: Callable[[Any], None],
  beforeRequest: Callable[[], Any] = None,
  reload: bool = False,
  **kwargs
) -> None:
  """
  Gets the data from either the cache synchronously or loads it
  asynchronously by calling "requests". You have to check yourself in the
  calling thread when the requests have finished!

  Parameters
  ----------
  fileDescription
      Dict from CdasWS.get_data_file() with keys Name, MimeType, StartTime,
      EndTime, Length and LastModified
  onDone
      Called when the data has been loaded either from cache (calling
      thread) or from requests (new thread). The first argument is True
      when the data was loaded from cache. The second argument is the
      result from the responses optionally passed through processResponse
  onError
      Called when there is an error and gets the error as first argument
  beforeRequest
      Called before a request is made in the calling thread
  reload
      When False (default), tries to read from cache and then executes the
      requests if reading failed. When True ignores the cache.
  kwargs
      Any remaining keyword arguments will be passed to CdasWs.download()
  """
  if isinstance(fileDescription, list):
    return [
      get(fd, onDone, onError, beforeRequest, reload, **kwargs)
      for fd in fileDescription
    ]

  cachedFile = (
    cacheFolder
    + re.search(r"/tmp/([^/]+/[^/]+)$", fileDescription["Name"]).group(1)
  )
  cachedFilePath = Path(cachedFile)

  def load():
    tempFile = None
    err = False
    for i in range(requestMaxRetries):
      err = False
      try:
        tempFile = cdas.download(
          fileDescription["Name"], fileDescription["Length"], **kwargs
        )
        break
      except Exception as e:
        err = e

    if (err or tempFile is None) and onError:
      if cachedFilePath.is_file():
        cdf = None
        cdfRead = False
        try:
          cdf = _read_del_invalid_CDF(cachedFile)
          cdfRead = True
        except Exception as e:
          pass
        if cdfRead:
          onDone(True, cdf)
          return
      onError(err if err else tempFile)
      return

    if not cachedFilePath.parent.exists():
      cachedFilePath.parent.mkdir()
    shutil.move(tempFile, cachedFile)

    cdf = None
    try:
      cdf = _read_del_invalid_CDF(cachedFile)
    except Exception as e:
      onError(e)
      return

    onDone(False, cdf)

  if not reload:
    if (cachedFilePath.is_file() and datetime.fromtimestamp(
        cachedFilePath.stat().st_mtime) >= datetime.fromisoformat(
          fileDescription["LastModified"].replace("Z", ""))):
      cdf = None
      cdfRead = False
      try:
        cdf = _read_del_invalid_CDF(cachedFile)
        cdfRead = True
      except Exception as e:
        onError(e)
      if cdfRead:
        onDone(True, cdf)
    else:
      reload = True

  if reload:
    if cachedFilePath.is_file():
      cachedFilePath.unlink()

    if beforeRequest:
      beforeRequest()

    t = Thread(target=load)
    t.daemon = True
    t.start()


def _read_del_invalid_CDF(file: str) -> cdflib.cdfread.CDF:
  try:
    return _read_CDF(file)
  except NotFoundError:
    p = Path(file)
    p.unlink()

    # clean up empty folder
    empty = True
    for child in p.parent.iterdir():
      empty = False
      break
    if empty:
      try:
        p.parent.rmdir()
      except OSError:
        pass
    raise


def _read_CDF(file: str) -> cdflib.cdfread.CDF:
  try:
    return cdflib.CDF(file)
  except OSError as e:
    if "is not a CDF file" in str(e):
      with open(file, mode="r") as f:
        content = f.read()
        if (content.startswith(("<!DOCTYPE HTML", "<html"))
            and "<title>404 Not Found</title>" in content):
          raise NotFoundError(file)
    raise


class NotFoundError(Exception):
  """Error raised when the CDF file was not found

  Attributes:
    file -- path to the file that was requested
  """
  def __init__(self, file: str):
    self.file = file

  def __str__(self):
    return "NotFoundError: File \"{}\" was not found on the server".format(
      re.sub(r"^(?:\.?[\\/])?cache\b", "", self.file)
    )
