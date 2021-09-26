# Models

This directory contains all reconstruction models this application can use.
Each model lives in its own folder to allow models that rely on multiple files,
maybe even models written in other languages.

You can have a look at the _dummy_ model if you want to add your own.
Basically the _folder_ gets imported in Python which means that your model class
should be defined in `__init__.py` as `Model` so it can be properly imported.
The _folder_ name must not include any spaces.
