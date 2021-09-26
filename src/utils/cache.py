import json
import re
from threading import Thread
from typing import List, Callable, Any, TypeVar, Generic, Union

from .constants import requestMaxRetries, cacheFolder

globalCache = {}

T = TypeVar("T")
TOptList = Union[T, List[T]]


class Cache(Generic[T]):
  def __init__(self, filename: str, writeToDisk=True):
    self.filename = re.sub(r"[/\\:*?\"<>|]", "_", filename)
    self.writeToDisk = writeToDisk

  def get(
    self,
    requests: Union[Callable[[], T], List[Callable[[], T]]],
    onDone: Callable[[bool, TOptList], None],
    onError: Callable[[], Any] = None,
    beforeRequest: Callable[[], Any] = None,
    processResponse: Callable[[TOptList], TOptList] = None,
    reload: bool = False
  ) -> None:
    """
    Gets the data from either the cache synchronously or loads it
    asynchronously by calling "requests". You have to check yourself in the
    calling thread when the requests have finished!

    Parameters
    ----------
    requests
      A single function or list of functions executing the requests and
      returning thier responses (new thread)
    onDone
      Called when the data has been loaded either from cache (calling
      thread) or from requests (new thread). The first argument is True
      when the data was loaded from cache. The second argument is the
      result from the responses optionally passed through processResponse
    onError
      Called when there was an error thrown from one of the request
      functions (new thread)
    beforeRequest
      Called before a request is made in the calling thread
    processResponse
      Called with all responses and should return the data that should be
      cached (new thread)
    reload
      When False (default), tries to read from cache and then executes the
      requests if reading failed. When True ignores the cache.
    """
    global globalCache
    wasNoList = False
    if not isinstance(requests, list):
      requests = [requests]
      wasNoList = True

    def load():
      responses = []
      for request in requests:
        res = None
        err = False
        for i in range(requestMaxRetries):
          err = False
          try:
            res = request()
            break
          except Exception as e:
            err = e

        if err and onError:
          onError(err)
          return

        responses.append(res)

      if len(responses) == 1 and wasNoList:
        responses = responses[0]
      if processResponse:
        responses = processResponse(responses)

      if self.writeToDisk:
        with open(cacheFolder + self.filename + ".json", "w") as f:
          json.dump(responses, f)
      else:
        globalCache[self.filename] = responses

      onDone(False, responses)

    if not reload:
      if self.writeToDisk:
        try:
          with open(cacheFolder + self.filename + ".json", "r") as f:
            onDone(True, json.load(f))
        except FileNotFoundError:
          reload = True
      elif self.filename in globalCache:
        onDone(True, globalCache[self.filename])
      else:
        reload = True

    if reload:
      if beforeRequest:
        beforeRequest()

      t = Thread(target=load)
      t.daemon = True
      t.start()
