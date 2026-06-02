# \# Function Generator Controller

# 

# A desktop application for controlling multi-channel VISA-compatible function 

# generators for dielectrophoresis (DEP), electrorotation (EROT), and 

# electroorientation (EOR) experiments.

# 

# \## Features

# \- EROT mode: 4-channel 90° phase quadrature frequency sweep

# \- DEP mode: synchronized 4-channel signal

# \- EOR mode: opposing electrode pair activation

# \- FREE mode: independent per-channel control

# \- Test mode: built-in virtual instrument (no hardware required)

# 

# \## Requirements

# ```bash

# pip install PyQt5 pyvisa pyvisa-py pyserial

# ```

# 

# \## Usage

# ```bash

# python function\_generator\_app.py          # normal mode

# python function\_generator\_app.py --test   # virtual instrument / test mode

# ```

# 

# \## Supported Instruments

# Any VISA-compatible function generator (USB, GPIB, or Serial interface).

# Tested with Keysight/Agilent series.

# 

# \## License

# MIT — see \[LICENSE](LICENSE)

