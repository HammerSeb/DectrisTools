# DectrisTools
Collection of tools for operating the DectrisQuadro camera in the Siwick Lab. Also contains code to manipulate the data taken with the detector.

You may install the package with
```
python -m pip install git+https://github.com/kremeyer/DectrisTools
```
I am currently developing it in a Python 3.10 environment.

## executable modules
run with `python -m DectrisTools.[module]`

* `liveview`: GUI application to monitor the data recorded with the detector in real time
* `statemonitor`: show live detector information
* `snapshot`: save the next image that will be recorded as an HDF5-file
* `single_shot_experiment`: start a single shot pump on/off experiment
* `process_single_shot`: process and reduce the raw data that you took with `single_shot_experiment`
