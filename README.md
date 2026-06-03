# Function Generator Controller

A desktop application for controlling multi-channel VISA-compatible function generators in microfluidic and dielectrophoretic experiments. Built for researchers who need precise, repeatable signal configurations without writing SCPI commands by hand.

---

## Experimental Modes

### Electrorotation (EROT)
Four channels in 90° phase quadrature (CH1: 0°, CH2: 90°, CH3: 180°, CH4: 270°). Define a comma-separated frequency list, set the applied potential (Vpp) and dwell time, and the app sweeps through each step automatically. Measured frequencies are read back from the instrument and logged. A **Summary only** checkbox suppresses individual SCPI lines and logs one clean line per step plus a final average.

### Dielectrophoresis (DEP)
All four channels output the same frequency, amplitude, and phase (0°). Set frequency and potential, click Apply.

### Electroorientation (EOR)
Activates one opposing electrode pair at a time: either CH1–CH3 or CH2–CH4. The active pair receives 0° and 180° respectively; the inactive pair is turned off. Switch between pairs at any time without disconnecting.

### Free Mode
Full independent control of each channel — individual frequency, amplitude, and phase. Channels can be individually enabled or disabled.

### DC Electrophoresis (DC EP)  *(Tabor WW5064)*
Applies a static DC offset voltage to selected channels for electrophoretic particle manipulation. DC is produced by setting the AC amplitude to the instrument minimum (10 mVpp) and applying `VOLT:OFFS`. Supports positive and negative voltages (±5 V into 50 Ω / ±10 V open circuit). Unselected channels have their offset zeroed and output turned off. A **Clear DC & Restore** button returns all channels to a safe AC-ready state before switching back to EROT / DEP / EOR.

---

## Features

- **SCPI over VISA** — works with any USB, GPIB, or Serial VISA instrument
- **Resizable layout** — horizontal splitter (live panel / tabs) and vertical splitter (work area / console) are fully user-adjustable
- **Live channel state panel** — shown for both real hardware and virtual instrument; displays channel frequency, amplitude, phase, and on/off state with a real-time waveform preview
- **Voltage-scaled waveform canvas** — Y-axis ticks scale to the actual applied voltage; DC channels render as flat lines
- **Live SCPI console** — timestamped log of every command and response, with a Clear button
- **Frequency sweep input** — comma-separated values with live validation and scientific notation support (`1e4`, `7e3`)
- **Virtual instrument / test mode** — built-in software simulator with realistic `FREQ?` noise and optional error injection; launch with `--test` flag or the Test Mode button
- **Verbose / summary logging** — toggle per-command SCPI lines or show one summary line per sweep step
- **Thread-safe worker** — all VISA I/O runs on a daemon thread behind a `threading.Lock`; the GUI stays responsive during sweeps and long dwells

---

## Screenshots

> *Add screenshots here after first run — `--test` mode works without any hardware.*

---

## Requirements

### Python environment
```bash
conda create -n fgcontroller python=3.11 -y
conda activate fgcontroller
pip install PyQt5 pyvisa pyvisa-py pyserial pyusb
```

### Instrument drivers (for real hardware)
| Interface | Driver needed |
|-----------|--------------|
| USB-VISA (`USB0::…`) | [Keysight IO Libraries](https://www.keysight.com/us/en/lib/software-detail/computer-software/io-libraries-suite-downloads-2175637.html) or [NI-VISA](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html) |
| GPIB (`GPIB0::…`) | NI-VISA + NI-488.2 |
| Serial/COM (`ASRL7::…`) | No extra driver — Windows native |

---

## Installation

### From source
```bash
git clone https://github.com/YOUR_USERNAME/function-generator-controller.git
cd function-generator-controller
pip install -r requirements.txt
python function_generator_app.py
```

### Pre-built Windows executable
Download `FunctionGeneratorController.exe` from the [latest release](../../releases/latest).

The executable is digitally signed via the [SignPath Foundation](https://signpath.io/free-for-open-source/) free code signing program for open source projects. No installation required, no Python needed on the target PC.

---

## Usage

```bash
# Connect to a real instrument
python function_generator_app.py

# Launch directly into test/virtual mode (no hardware needed)
python function_generator_app.py --test
```

### Finding your VISA address
Click **Scan Ports** in the connection panel, or from a Python prompt:

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

Common formats:
| Format | Interface |
|--------|-----------|
| `USB0::0x0957::0x1507::MY57001222::0::INSTR` | USB-VISA |
| `GPIB0::11::INSTR` | GPIB |
| `ASRL7::INSTR` | Serial (COM7) |

---

## Tested Instruments

| Instrument | Modes supported |
|-----------|----------------|
| Tabor Electronics WW5064 | EROT, DEP, EOR, FREE, DC EP |
| Any VISA-compatible multi-channel generator | EROT, DEP, EOR, FREE |

---

## Building the Executable

Requires PyInstaller (`pip install pyinstaller`):

```bash
pyinstaller --onefile --windowed \
  --name "FunctionGeneratorController" \
  --hidden-import="pyvisa_py" \
  --hidden-import="pyvisa_py.protocols" \
  --hidden-import="pyvisa_py.sessions" \
  --hidden-import="pyvisa_py.tcpip" \
  --hidden-import="pyvisa_py.serial" \
  --hidden-import="pyvisa_py.usb" \
  --hidden-import="serial" \
  --hidden-import="serial.tools" \
  --hidden-import="serial.tools.list_ports" \
  --hidden-import="usb.core" \
  --hidden-import="usb.backend.libusb1" \
  function_generator_app.py
```

Signed releases are produced automatically via the GitHub Actions + SignPath pipeline on every version tag.

---

## Project Structure

```
function-generator-controller/
├── function_generator_app.py   # entire application (single file)
├── requirements.txt            # Python dependencies
├── README.md
├── LICENSE                     # MIT
└── .github/
    └── workflows/
        └── build.yml           # PyInstaller + SignPath CI pipeline
```

---

## Architecture Notes

```
MainWindow (PyQt5 GUI thread)
│
├── ConnectionPanel       — VISA address, buffer, timeout, connect/disconnect/test
├── QSplitter (vertical)
│   ├── QSplitter (horizontal)
│   │   ├── LivePanel     — channel state + waveform preview (real & virtual)
│   │   └── QTabWidget
│   │       ├── EROTTab   — frequency sweep with 90° quadrature
│   │       ├── DEPTab    — single-frequency DEP signal
│   │       ├── EORTab    — opposing electrode pair selection
│   │       ├── FreeTab   — per-channel independent control
│   │       └── DCTab     — DC electrophoresis (Tabor WW5064)
│   └── Console           — timestamped SCPI log
│
└── InstrumentWorker (QObject)
    ├── VirtualInstrument — software simulator (test mode)
    ├── threading.Lock    — serialises all VISA access
    └── daemon threads    — run_erot / run_dep / run_eor / run_free / run_dc
```

`InstrumentWorker` is a plain `QObject` — no `QThread`. All long-running methods are dispatched via `threading.Thread(daemon=True)`. Qt signals carry results back to the GUI thread via queued connections.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for significant changes.

Things that would be useful:
- Support for additional instrument families (Rigol, Tektronix, Stanford Research)
- Saving and loading experiment configurations (JSON)
- Exporting sweep logs to CSV
- Frequency sweep progress bar

---

## License

MIT — see [LICENSE](LICENSE).

---

## Citation

If you use this software in published research, please cite it:

```
Author. (Year). Function Generator Controller (Version X.X) [Software].
GitHub. https://github.com/YOUR_USERNAME/function-generator-controller
```

A `CITATION.cff` file is provided for automatic citation in GitHub and Zenodo.