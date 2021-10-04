# IMARR - An Interface for Magnetic Flux Rope Reconstructions

This is an interface to ease the workflow of reconstructing magnetic flux ropes measured by various spacecrafts.

# Requirements
* python 3.7
* tkinter
* cdasws: [pypi.org](https://pypi.org/project/cdasws/) | [anaconda.org](https://anaconda.org/spdf.gsfc.nasa.gov/cdasws)
* cdflib: [pypi.org](https://pypi.org/project/cdflib/) | [anaconda.org](https://anaconda.org/mavensdc/cdflib)
* astropy: [pypi.org](https://pypi.org/project/astropy/) | [anaconda.org](https://anaconda.org/conda-forge/astropy)
* numpy: [pypi.org](https://pypi.org/project/numpy/) | [anaconda.org](https://anaconda.org/conda-forge/numpy)
* matplotlib: [pypi.org](https://pypi.org/project/matplotlib/) | [anaconda.org](https://anaconda.org/conda-forge/matplotlib)
* scipy: [pypi.org](https://pypi.org/project/scipy/) | [anaconda.org](https://anaconda.org/conda-forge/scipy) (only for the _Lundquist model_, the program can be run without it)

# Installation
1. Clone the repo
1. Install all dependencies

# Execute
```
python imarr.py
```

# Know problems
The implemented reconstruction methods are not good. Currently they assume that the spacecraft has passed the center of the flux rope which is not the case in most encounters.

# Ideas for further development
## General
* display models in grid, not only column
* remove models that never ran from model runner (or add button to let the user remove it)
* import data (no download)

## PlotSelection
* button to change plot labels/margins
* change plot height

# Development
Just clone the repo to develop it further. The different _pages_ are in `src/pages`. The program calls the models by an API which is outlined in the [_Dummy model_](./src/models/dummy).

If there are any issues, just open an issue. PRs are welcome too!
