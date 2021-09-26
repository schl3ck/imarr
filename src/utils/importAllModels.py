from importlib import import_module, invalidate_caches, reload
import os
from typing import Any, Dict
import types

knownModules: Dict[str, Any] = {}


def importAllModels(refresh=False):
  invalidate_caches()
  l = []
  with os.scandir("src/models") as it:
    for i in it:
      if i.is_dir() and not i.name.startswith("__"):
        if i.name in knownModules:
          module = knownModules[i.name]
          if refresh:
            reload_package(module)
        else:
          module = import_module("src.models." + i.name)
          knownModules[i.name] = module
        l.append(module.Model)
  return l


def reload_package(package):
  """
  Copied from https://stackoverflow.com/a/28516918
  Modified
  """
  assert (hasattr(package, "__package__"))
  fn = package.__file__
  fn_dir = os.path.dirname(fn) + os.sep
  module_visit = {fn}
  del fn

  def reload_recursive_ex(module):
    for module_child in vars(module).values():
      if isinstance(module_child, types.ModuleType):
        fn_child = getattr(module_child, "__file__", None)
        if (fn_child is not None) and fn_child.startswith(fn_dir):
          if fn_child not in module_visit:
            module_visit.add(fn_child)
            reload_recursive_ex(module_child)
    # reload last to have reloaded all child modules before
    reload(module)

  return reload_recursive_ex(package)
