"""
Function Generator Control App
================================
Controls a multi-channel VISA-compatible function generator
for DEP / EROT / EOR experiments.

Requirements:
    pip install PyQt5 pyvisa pyvisa-py

Run:
    python function_generator_app.py
    python function_generator_app.py --test   # launch straight into test/virtual mode
"""

import sys
import time
import threading
import random
import math
import pyvisa
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox,
    QTextEdit, QGroupBox, QTabWidget, QFrame, QDoubleSpinBox,
    QSpinBox, QCheckBox, QSizePolicy, QMessageBox, QScrollArea,
    QSlider, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QTextCursor

# ─────────────────────────────────────────────────────────────
#  STYLESHEET  (dark oscilloscope aesthetic)
# ─────────────────────────────────────────────────────────────
STYLE = """
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    background: #161b22;
}
QTabBar::tab {
    background: #0d1117;
    color: #8b949e;
    padding: 8px 20px;
    border: 1px solid #30363d;
    border-bottom: none;
    font-weight: bold;
    letter-spacing: 1px;
    font-size: 11px;
}
QTabBar::tab:selected {
    background: #161b22;
    color: #58a6ff;
    border-top: 2px solid #58a6ff;
}
QTabBar::tab:hover:!selected { color: #c9d1d9; background: #1c2128; }

QGroupBox {
    border: 1px solid #30363d;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: bold;
    color: #8b949e;
    letter-spacing: 1px;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #58a6ff;
}
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 7px 16px;
    font-weight: bold;
    letter-spacing: 0.5px;
}
QPushButton:hover { background-color: #30363d; color: #fff; }
QPushButton:pressed { background-color: #388bfd22; border-color: #58a6ff; }
QPushButton:disabled { color: #484f58; border-color: #21262d; }
QPushButton#btn_connect    { background:#1a4a1a; border-color:#238636; color:#3fb950; }
QPushButton#btn_connect:hover { background:#1f6623; }
QPushButton#btn_disconnect { background:#4a1a1a; border-color:#da3633; color:#f85149; }
QPushButton#btn_disconnect:hover { background:#6e2222; }
QPushButton#btn_start {
    background:#0d419d; border-color:#388bfd; color:#58a6ff;
    font-size:14px; padding:10px 24px;
}
QPushButton#btn_start:hover { background:#1158c7; }
QPushButton#btn_stop {
    background:#6e2222; border-color:#da3633; color:#f85149;
    font-size:14px; padding:10px 24px;
}
QPushButton#btn_stop:hover { background:#922a2a; }
QPushButton#btn_output_on  { background:#1a4a1a; border-color:#238636; color:#3fb950; }
QPushButton#btn_output_off { background:#4a1a1a; border-color:#da3633; color:#f85149; }
QPushButton#btn_testmode {
    background:#2a1a4a; border-color:#8957e5; color:#d2a8ff;
    font-weight:bold; letter-spacing:1px;
}
QPushButton#btn_testmode:hover  { background:#3d2470; }
QPushButton#btn_testmode_active {
    background:#3d2470; border-color:#d2a8ff; color:#d2a8ff;
    font-weight:bold;
}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background:#0d1117; border:1px solid #30363d; border-radius:3px;
    color:#c9d1d9; padding:5px 8px; selection-background-color:#388bfd;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border-color:#58a6ff;
}
QComboBox::drop-down { border:none; }
QComboBox QAbstractItemView {
    background:#161b22; border:1px solid #30363d;
    selection-background-color:#388bfd;
}
QTextEdit {
    background:#0d1117; border:1px solid #30363d; border-radius:3px;
    color:#3fb950; font-family:'Consolas',monospace; font-size:12px; padding:6px;
}
QLabel#ch1 { color:#f7c948; }
QLabel#ch2 { color:#58a6ff; }
QLabel#ch3 { color:#3fb950; }
QLabel#ch4 { color:#f85149; }
QLabel#status_ok   { color:#3fb950; font-weight:bold; }
QLabel#status_test { color:#d2a8ff; font-weight:bold; }
QLabel#status_err  { color:#f85149; font-weight:bold; }
QLabel#status_idle { color:#8b949e; }
QFrame#separator   { background:#30363d; max-height:1px; margin:4px 0; }
QSlider::groove:horizontal { height:4px; background:#30363d; border-radius:2px; }
QSlider::handle:horizontal {
    background:#58a6ff; width:14px; height:14px; margin:-5px 0; border-radius:7px;
}
QSlider::sub-page:horizontal { background:#388bfd; border-radius:2px; }

QSplitter::handle:horizontal {
    background: #30363d;
    width: 4px;
}
QSplitter::handle:horizontal:hover { background: #58a6ff; }
QSplitter::handle:vertical {
    background: #30363d;
    height: 4px;
}
QSplitter::handle:vertical:hover { background: #58a6ff; }
"""

CH_COLORS = {1: '#f7c948', 2: '#58a6ff', 3: '#3fb950', 4: '#f85149'}


# ─────────────────────────────────────────────────────────────
#  VIRTUAL INSTRUMENT  (test mode — no hardware needed)
# ─────────────────────────────────────────────────────────────
class VirtualChannel:
    """Simulates a single output channel."""
    def __init__(self, ch: int):
        self.ch      = ch
        self.freq    = 1000.0
        self.volt    = 1.0
        self.phase   = 0.0
        self.enabled = False

    def summary(self):
        state = "ON " if self.enabled else "OFF"
        return (f"CH{self.ch} [{state}]  "
                f"{self.freq:>12.3f} Hz  "
                f"{self.volt:.3f} Vpp  "
                f"{self.phase:>6.1f}°")


class VirtualInstrument:
    """
    Drop-in replacement for a real VISA instrument.
    Simulates command parsing, realistic noise on FREQ?, small
    latency, and occasional (rare) comms errors to stress-test the UI.
    """
    IDN = "VIRTUAL,FG-4CH-SIM,SN00000,FW1.0.0"

    def __init__(self, error_rate: float = 0.0):
        self._channels   = {i: VirtualChannel(i) for i in range(1, 5)}
        self._active_ch  = 1
        self._error_rate = error_rate   # 0.0 … 1.0, probability of a fake comms error
        self._closed     = False
        self.timeout     = 5000
        self.chunk_size  = 1024
        self.read_termination  = '\n'
        self.write_termination = '\n'

    def _maybe_fail(self):
        if self._error_rate > 0 and random.random() < self._error_rate:
            raise IOError("VIRTUAL: simulated communications error")

    def write(self, cmd: str):
        self._maybe_fail()
        time.sleep(0.005)          # simulate bus latency
        cmd = cmd.strip()

        if cmd.startswith(':INST:SEL'):
            try:
                self._active_ch = int(cmd.split()[-1])
            except ValueError:
                pass
        elif cmd.startswith('FREQ '):
            self._channels[self._active_ch].freq = float(cmd.split()[1])
        elif cmd.startswith('VOLT '):
            self._channels[self._active_ch].volt = float(cmd.split()[1])
        elif 'PHASe' in cmd:
            self._channels[self._active_ch].phase = float(cmd.split()[-1])
        elif cmd == 'OUTP ON':
            self._channels[self._active_ch].enabled = True
        elif cmd == 'OUTP OFF':
            self._channels[self._active_ch].enabled = False

    def query(self, cmd: str) -> str:
        self._maybe_fail()
        time.sleep(0.010)
        cmd = cmd.strip()
        if cmd == '*IDN?':
            return self.IDN
        if cmd == 'FREQ?':
            ch   = self._channels[self._active_ch]
            # add ±0.01 % noise so queries look realistic
            noise = ch.freq * random.uniform(-0.0001, 0.0001)
            return f"{ch.freq + noise:.6f}"
        return "0"

    def close(self):
        self._closed = True

    def state_snapshot(self) -> list[str]:
        """Returns human-readable channel state lines for the test panel."""
        return [ch.summary() for ch in self._channels.values()]


# ─────────────────────────────────────────────────────────────
#  INSTRUMENT WORKER
#  - Pure Python object (no QThread), all heavy methods called
#    from daemon threads via threading.Thread.
#  - A threading.Lock serialises every VISA / virtual call so
#    connect / disconnect / run_* never race each other.
# ─────────────────────────────────────────────────────────────
class InstrumentWorker(QObject):
    log_signal   = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    done_signal  = pyqtSignal(str)          # carries mode string: 'erot'|'dep'|'eor'|'free'
    freq_signal  = pyqtSignal(int, float)   # (step_index, measured_freq)

    def __init__(self):
        super().__init__()
        self.rm         = None
        self.inst       = None              # real Resource OR VirtualInstrument
        self._lock      = threading.Lock()
        self._stop_flag = False
        self._test_mode = False

    # ── connection ──────────────────────────────────────────
    def connect(self, resource_string: str, buffer_size: int = 1024,
                timeout_ms: int = 5000) -> bool:
        try:
            with self._lock:
                self.rm   = pyvisa.ResourceManager()
                self.inst = self.rm.open_resource(resource_string)
                self.inst.read_termination  = '\n'
                self.inst.write_termination = '\n'
                self.inst.timeout    = timeout_ms
                self.inst.chunk_size = buffer_size
                idn = self.inst.query('*IDN?').strip()
            self._test_mode = False
            self.log_signal.emit(f"[CONNECTED] {idn}")
            return True
        except Exception as e:
            self.error_signal.emit(f"[ERROR] Connection failed: {e}")
            return False

    def connect_virtual(self, error_rate: float = 0.0) -> bool:
        """Connect to the built-in virtual instrument (no hardware required)."""
        with self._lock:
            self.inst = VirtualInstrument(error_rate=error_rate)
            self.rm   = None
        self._test_mode = True
        self.log_signal.emit(
            f"[TEST MODE] Virtual instrument connected  "
            f"(error_rate={error_rate*100:.0f}%)"
        )
        return True

    def disconnect(self):
        self._stop_flag = True          # halt any running sweep first
        try:
            with self._lock:
                if self.inst:
                    try:
                        self.inst.write('OUTP OFF')
                    except Exception:
                        pass
                    self.inst.close()
                if self.rm:
                    self.rm.close()
                self.inst = None
                self.rm   = None
            self._test_mode = False
            self.log_signal.emit("[DISCONNECTED]")
        except Exception as e:
            self.error_signal.emit(f"[ERROR] Disconnect: {e}")

    def list_resources(self) -> list:
        try:
            rm  = pyvisa.ResourceManager()
            res = rm.list_resources()
            rm.close()
            return list(res)
        except Exception as e:
            self.error_signal.emit(f"[ERROR] Listing resources: {e}")
            return []

    # ── low-level helpers ────────────────────────────────────
    def _write(self, cmd: str, verbose: bool = True):
        if not self.inst:
            self.error_signal.emit("[ERROR] No instrument connected.")
            return
        with self._lock:
            self.inst.write(cmd)
        if verbose:
            self.log_signal.emit(f"  >> {cmd}")

    def _query(self, cmd: str, verbose: bool = True) -> str:
        if not self.inst:
            self.error_signal.emit("[ERROR] No instrument connected.")
            return "0"
        with self._lock:
            resp = self.inst.query(cmd).strip()
        if verbose:
            self.log_signal.emit(f"  >> {cmd}  <<  {resp}")
        return resp

    def _sel(self, ch: int, verbose: bool = True):
        self._write(f':INST:SEL {ch}', verbose=verbose)

    def _setup_channel(self, ch: int, freq_hz: float, volt: float, phase_deg: float,
                        verbose: bool = True):
        self._sel(ch, verbose=verbose)
        self._write(f'FREQ {freq_hz}', verbose=verbose)
        self._write(f'VOLT {volt}', verbose=verbose)
        self._write(f'SINusoid:PHASe {phase_deg}', verbose=verbose)
        self._write('OUTP ON', verbose=verbose)

    # ── output master switch ─────────────────────────────────
    def all_output(self, state: bool):
        if not self.inst:
            self.error_signal.emit("[ERROR] No instrument connected.")
            return
        cmd = 'ON' if state else 'OFF'
        for ch in range(1, 5):
            self._sel(ch)
            self._write(f'OUTP {cmd}')
        self.log_signal.emit(f"[OUTPUT {'ON' if state else 'OFF'}] all channels")

    # ── EROT sweep ───────────────────────────────────────────
    def run_erot(self, frequencies: list, volt: float, dwell_s: float,
                 summary_only: bool = False):
        """4-channel 90° phase quadrature sweep.

        summary_only: when True, individual SCPI command lines are suppressed;
        only one summary line per step is logged (with the measured frequency).
        """
        self._stop_flag = False
        phases = [0, 90, 180, 270]
        verbose = not summary_only
        measured = []
        try:
            self.log_signal.emit("[EROT] Starting sweep …")
            for idx, freq in enumerate(frequencies):
                if self._stop_flag or not self.inst:
                    self.log_signal.emit("[EROT] Sweep aborted (stop or disconnect).")
                    break
                for ch, phase in enumerate(phases, start=1):
                    self._setup_channel(ch, freq, volt, phase, verbose=verbose)
                # query measured freq on CH1
                self._sel(1, verbose=verbose)
                meas = float(self._query('FREQ?', verbose=verbose))
                measured.append(meas)
                self.freq_signal.emit(idx, meas)
                # one clean summary line regardless of verbosity
                self.log_signal.emit(
                    f"[EROT] Step {idx+1}/{len(frequencies)}  "
                    f"set={freq:.3f} Hz  meas={meas:.3f} Hz"
                )
                # dwell — no countdown, just sleep
                elapsed = 0
                while elapsed < dwell_s:
                    if self._stop_flag:
                        break
                    time.sleep(min(1.0, dwell_s - elapsed))
                    elapsed += 1.0
            if not self._stop_flag:
                self.all_output(False)
            if measured:
                avg = sum(measured) / len(measured)
                self.log_signal.emit(
                    f"[EROT] Sweep complete — "
                    f"{len(measured)} steps  avg measured={avg:.3f} Hz"
                )
            else:
                self.log_signal.emit("[EROT] Sweep complete.")
        except Exception as e:
            self.error_signal.emit(f"[EROT ERROR] {e}")
        finally:
            self.done_signal.emit("erot")

    # ── DEP ──────────────────────────────────────────────────
    def run_dep(self, freq: float, volt: float):
        """All 4 channels same freq, same phase (0°)."""
        self._stop_flag = False
        try:
            if not self.inst:
                self.log_signal.emit("[DEP] Aborted — no instrument connected.")
                return
            self.log_signal.emit(f"[DEP] f={freq} Hz  V={volt} Vpp")
            for ch in range(1, 5):
                self._setup_channel(ch, freq, volt, 0)
            self.log_signal.emit("[DEP] Applied.")
        except Exception as e:
            self.error_signal.emit(f"[DEP ERROR] {e}")
        finally:
            self.done_signal.emit("dep")

    # ── EOR ──────────────────────────────────────────────────
    def run_eor(self, pair: str, freq: float, volt: float):
        """
        pair='13': CH1 ON (0°), CH3 ON (180°), CH2/4 OFF
        pair='24': CH2 ON (0°), CH4 ON (180°), CH1/3 OFF
        """
        self._stop_flag = False
        try:
            if not self.inst:
                self.log_signal.emit("[EOR] Aborted — no instrument connected.")
                return
            active   = (1, 3) if pair == '13' else (2, 4)
            inactive = (2, 4) if pair == '13' else (1, 3)
            self.log_signal.emit(
                f"[EOR] pair={pair}  f={freq} Hz  V={volt} Vpp"
            )
            for ch in inactive:
                self._sel(ch)
                self._write('OUTP OFF')
            for ch, ph in zip(active, [0, 180]):
                self._setup_channel(ch, freq, volt, ph)
            self.log_signal.emit(
                f"[EOR] CH{active[0]} (0°) and CH{active[1]} (180°) active."
            )
        except Exception as e:
            self.error_signal.emit(f"[EOR ERROR] {e}")
        finally:
            self.done_signal.emit("eor")

    # ── FREE mode ────────────────────────────────────────────
    def run_free(self, channels: list):
        """channels: list of dicts {ch, freq, volt, phase, enabled}"""
        self._stop_flag = False
        try:
            if not self.inst:
                self.log_signal.emit("[FREE] Aborted — no instrument connected.")
                return
            self.log_signal.emit("[FREE] Applying custom channel settings …")
            for cfg in channels:
                self._sel(cfg['ch'])
                if cfg['enabled']:
                    self._write(f"FREQ {cfg['freq']}")
                    self._write(f"VOLT {cfg['volt']}")
                    self._write(f"SINusoid:PHASe {cfg['phase']}")
                    self._write('OUTP ON')
                else:
                    self._write('OUTP OFF')
            self.log_signal.emit("[FREE] Done.")
        except Exception as e:
            self.error_signal.emit(f"[FREE ERROR] {e}")
        finally:
            self.done_signal.emit("free")

    def stop(self):
        self._stop_flag = True

    def reset(self):
        """Clear the stop flag before launching any new command."""
        self._stop_flag = False

    # ── test-mode helpers ────────────────────────────────────
    def get_virtual_state(self) -> list:
        """Returns channel state summary lines under the lock."""
        with self._lock:
            if self._test_mode and isinstance(self.inst, VirtualInstrument):
                return self.inst.state_snapshot()
        return []

    def get_virtual_channels(self) -> list:
        """Returns a snapshot list of VirtualChannel objects under the lock.
        Safe to read from the UI thread while worker threads are mutating state."""
        with self._lock:
            if self._test_mode and isinstance(self.inst, VirtualInstrument):
                # Return shallow copies so the canvas never reads a partially
                # mutated object after we release the lock.
                import copy
                return [copy.copy(ch) for ch in self.inst._channels.values()]
        return []


# ─────────────────────────────────────────────────────────────
#  SHARED UI HELPERS
# ─────────────────────────────────────────────────────────────
def ch_label(n: int, text: str = '') -> QLabel:
    lbl = QLabel(text or f'CH{n}')
    lbl.setObjectName(f'ch{n}')
    lbl.setStyleSheet(f"color:{CH_COLORS[n]}; font-weight:bold;")
    return lbl


def hsep() -> QFrame:
    f = QFrame()
    f.setObjectName("separator")
    f.setFrameShape(QFrame.HLine)
    return f


# ─────────────────────────────────────────────────────────────
#  FREQ LIST EDITOR  (EROT)  — comma-separated text input
# ─────────────────────────────────────────────────────────────
class FreqListEditor(QWidget):
    """
    Simple comma-separated frequency entry.
    Type values like:  10000, 7000, 5000, 3000, 2000, 1500
    Supports scientific notation: 1e4, 7e3, 5e3
    Invalid tokens are highlighted; the parsed count is shown live.
    """
    DEFAULT = "10000, 7000, 5000, 3000, 2000, 1500"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # header row
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Frequencies (Hz), comma-separated:"))
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#8b949e; font-size:11px;")
        hdr.addStretch()
        hdr.addWidget(self._count_lbl)
        layout.addLayout(hdr)

        # text field
        self._edit = QLineEdit(self.DEFAULT)
        self._edit.setPlaceholderText("e.g.  10000, 7000, 5e3, 1000.5")
        self._edit.setToolTip(
            "Enter frequency values in Hz separated by commas.\n"
            "Scientific notation is supported (e.g. 1e4 = 10 000 Hz)."
        )
        layout.addWidget(self._edit)

        # validation feedback label
        self._warn_lbl = QLabel("")
        self._warn_lbl.setStyleSheet("color:#f85149; font-size:11px;")
        self._warn_lbl.setVisible(False)
        layout.addWidget(self._warn_lbl)

        self._edit.textChanged.connect(self._on_text_changed)
        self._on_text_changed(self.DEFAULT)

    def _on_text_changed(self, text: str):
        freqs, bad = self._parse(text)
        n = len(freqs)
        if bad:
            self._count_lbl.setText(f"{n} valid  |  {len(bad)} invalid")
            self._count_lbl.setStyleSheet("color:#f85149; font-size:11px;")
            self._warn_lbl.setText(f"Ignored tokens: {', '.join(bad)}")
            self._warn_lbl.setVisible(True)
            self._edit.setStyleSheet("border:1px solid #da3633;")
        else:
            self._count_lbl.setText(f"{n} step{'s' if n != 1 else ''}")
            self._count_lbl.setStyleSheet("color:#3fb950; font-size:11px;")
            self._warn_lbl.setVisible(False)
            self._edit.setStyleSheet("")

    @staticmethod
    def _parse(text: str):
        good, bad = [], []
        for token in text.split(','):
            token = token.strip()
            if not token:
                continue
            try:
                val = float(token)
                if val <= 0:
                    raise ValueError
                good.append(val)
            except ValueError:
                bad.append(token)
        return good, bad

    def get_frequencies(self) -> list:
        freqs, _ = self._parse(self._edit.text())
        return freqs


# ─────────────────────────────────────────────────────────────
#  CONSOLE
# ─────────────────────────────────────────────────────────────
class Console(QGroupBox):
    def __init__(self):
        super().__init__("CONSOLE")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(60)   # can shrink but not disappear
        # no setFixedHeight — the splitter controls the size
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self.text.clear)
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(btn_clear)
        layout.addLayout(top)
        layout.addWidget(self.text)

    def log(self, msg: str, color: str = '#3fb950'):
        ts = time.strftime('%H:%M:%S')
        self.text.append(
            f'<span style="color:#484f58">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self.text.moveCursor(QTextCursor.End)

    def error(self, msg: str):
        self.log(msg, color='#f85149')


# ─────────────────────────────────────────────────────────────
#  CONNECTION PANEL
# ─────────────────────────────────────────────────────────────
class ConnectionPanel(QGroupBox):
    connect_clicked    = pyqtSignal(str, int, int)
    disconnect_clicked = pyqtSignal()
    scan_clicked       = pyqtSignal()
    test_clicked       = pyqtSignal(float)   # error_rate

    def __init__(self):
        super().__init__("INSTRUMENT CONNECTION")
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(8, 6, 8, 6)
        vbox.setSpacing(5)

        # ── ROW 1: adjustable parameters ────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        row1.addWidget(QLabel("VISA Resource:"))
        self.addr_edit = QLineEdit("ASRL7::INSTR")
        self.addr_edit.setPlaceholderText("USB0::…  /  GPIB0::xx::INSTR  /  ASRL7::INSTR")
        row1.addWidget(self.addr_edit, stretch=1)   # takes all remaining space

        row1.addSpacing(8)
        row1.addWidget(QLabel("Buffer:"))
        self.buf_spin = QSpinBox()
        self.buf_spin.setRange(256, 65536)
        self.buf_spin.setValue(1024)
        self.buf_spin.setSingleStep(256)
        self.buf_spin.setFixedWidth(82)
        row1.addWidget(self.buf_spin)

        row1.addSpacing(8)
        row1.addWidget(QLabel("Timeout (ms):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(500, 60000)
        self.timeout_spin.setValue(5000)
        self.timeout_spin.setSingleStep(500)
        self.timeout_spin.setFixedWidth(76)
        row1.addWidget(self.timeout_spin)

        vbox.addLayout(row1)

        # ── ROW 2: connection & test-mode buttons + status ──
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        self.btn_scan = QPushButton("🔍 Scan Ports")
        self.btn_conn = QPushButton("⚡ Connect")
        self.btn_conn.setObjectName("btn_connect")
        self.btn_disc = QPushButton("✕ Disconnect")
        self.btn_disc.setObjectName("btn_disconnect")
        self.btn_disc.setEnabled(False)

        row2.addWidget(self.btn_scan)
        row2.addWidget(self.btn_conn)
        row2.addWidget(self.btn_disc)
        row2.addSpacing(16)

        self.btn_test = QPushButton("🧪 Test Mode")
        self.btn_test.setObjectName("btn_testmode")
        self.err_spin = QDoubleSpinBox()
        self.err_spin.setRange(0.0, 0.5)
        self.err_spin.setValue(0.0)
        self.err_spin.setSingleStep(0.05)
        self.err_spin.setDecimals(2)
        self.err_spin.setSuffix(" err%")
        self.err_spin.setFixedWidth(96)
        self.err_spin.setToolTip(
            "Probability (0–50 %) that each virtual command raises a fake\n"
            "comms error — useful for stress-testing error handling."
        )
        row2.addWidget(self.btn_test)
        row2.addWidget(self.err_spin)

        row2.addStretch()

        self.status_lbl = QLabel("● Not connected")
        self.status_lbl.setObjectName("status_idle")
        row2.addWidget(self.status_lbl)

        vbox.addLayout(row2)

        self.btn_scan.clicked.connect(self.scan_clicked)
        self.btn_conn.clicked.connect(self._on_connect)
        self.btn_disc.clicked.connect(self.disconnect_clicked)
        self.btn_test.clicked.connect(self._on_test)

    def _on_connect(self):
        self.connect_clicked.emit(
            self.addr_edit.text(),
            self.buf_spin.value(),
            self.timeout_spin.value()
        )

    def _on_test(self):
        self.test_clicked.emit(self.err_spin.value())

    def set_connected(self, ok: bool, test_mode: bool = False):
        if ok and test_mode:
            self.status_lbl.setText("● TEST MODE — Virtual Instrument")
            self.status_lbl.setObjectName("status_test")
            self.btn_test.setObjectName("btn_testmode_active")
            self.btn_test.setEnabled(False)
        elif ok:
            self.status_lbl.setText("● Connected")
            self.status_lbl.setObjectName("status_ok")
            self.btn_test.setObjectName("btn_testmode")
            self.btn_test.setEnabled(False)
        else:
            self.status_lbl.setText("● Not connected")
            self.status_lbl.setObjectName("status_idle")
            self.btn_test.setObjectName("btn_testmode")
            self.btn_test.setEnabled(True)
        # force style refresh
        for w in [self.status_lbl, self.btn_test]:
            w.style().unpolish(w)
            w.style().polish(w)
        self.btn_conn.setEnabled(not ok)
        self.btn_disc.setEnabled(ok)

    def populate_resources(self, resources: list):
        if resources:
            self.addr_edit.setText(resources[0])


# ─────────────────────────────────────────────────────────────
#  TEST MODE PANEL  (virtual instrument state viewer)
# ─────────────────────────────────────────────────────────────
class TestModePanel(QGroupBox):
    """
    Floating panel shown only in test mode.
    Polls the VirtualInstrument every second and renders
    a live channel state table plus a mini oscilloscope preview.
    """
    def __init__(self, worker: 'InstrumentWorker'):
        super().__init__("🧪  VIRTUAL INSTRUMENT — LIVE STATE")
        self._worker = worker
        layout = QVBoxLayout(self)

        # header note
        note = QLabel(
            "No hardware connected. All SCPI commands are processed by the built-in "
            "virtual instrument. Channel state below updates in real-time."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#d2a8ff; font-size:11px;")
        layout.addWidget(note)

        # channel state labels
        self._ch_labels: dict[int, QLabel] = {}
        ch_grid = QGridLayout()
        for ch in range(1, 5):
            badge = ch_label(ch)
            badge.setFixedWidth(40)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(f"color:{CH_COLORS[ch]}; font-family:Consolas;")
            ch_grid.addWidget(badge, ch - 1, 0)
            ch_grid.addWidget(val_lbl, ch - 1, 1)
            self._ch_labels[ch] = val_lbl
        layout.addLayout(ch_grid)

        # waveform canvas (pure Qt, no matplotlib dependency)
        self._canvas = WaveformCanvas()
        layout.addWidget(self._canvas)

        # auto-refresh timer
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh)

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _refresh(self):
        lines = self._worker.get_virtual_state()
        if not lines:
            return
        chans = self._worker.get_virtual_channels()
        if not chans:
            return
        for ch in range(1, 5):
            self._ch_labels[ch].setText(lines[ch - 1])
        self._canvas.update_channels(chans)


# ─────────────────────────────────────────────────────────────
#  WAVEFORM CANVAS  (pure Qt — no extra dependencies)
# ─────────────────────────────────────────────────────────────
class WaveformCanvas(QWidget):
    """
    Time-domain oscilloscope preview for all 4 virtual channels.

    Layout
    ──────
    Left margin (Y_MARGIN px) contains:
      • a solid Y-axis line
      • ±Vpeak tick marks scaled to the highest active channel voltage
      • numeric voltage labels (Vpp / 2)
    Plot area to the right shows 3 cycles of the fastest active channel.
    Disabled channels are drawn as a faint dashed zero line.
    """

    Y_MARGIN = 52   # pixels reserved for Y-axis labels

    def __init__(self):
        super().__init__()
        self._channels: list = []
        self.setMinimumHeight(140)
        self.setStyleSheet(
            "background:#0a0e14; border:1px solid #30363d; border-radius:3px;"
        )

    def update_channels(self, channels):
        self._channels = channels
        self.update()

    # ── helpers ──────────────────────────────────────────────
    @staticmethod
    def _nice_voltage(v: float) -> str:
        """Format a voltage value concisely: '1.00', '500m', etc."""
        if abs(v) >= 1.0:
            return f"{v:.2f}"
        return f"{v*1000:.0f}m"

    # ── paint ────────────────────────────────────────────────
    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QPen, QColor, QFont
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        M = self.Y_MARGIN          # left margin width
        PW = W - M                 # plot area width
        mid = H / 2.0              # vertical centre

        # ── font for axis labels ──────────────────────────────
        lbl_font = QFont("Consolas", 8)
        p.setFont(lbl_font)

        # ── background + grid (plot area only) ───────────────
        p.fillRect(0, 0, W, H, QColor("#0a0e14"))
        p.setPen(QPen(QColor("#1a2030"), 1))
        step = 40
        x = M
        while x < W:
            p.drawLine(int(x), 0, int(x), H)
            x += step
        y = 0
        while y < H:
            p.drawLine(M, int(y), W, int(y))
            y += step

        # ── placeholder messages ──────────────────────────────
        if not self._channels:
            p.setPen(QPen(QColor("#484f58"), 1))
            p.drawText(M + PW // 2 - 50, int(mid) + 4, "No signal data")
            p.end()
            return

        active = [c for c in self._channels if c.enabled]
        if not active:
            p.setPen(QPen(QColor("#484f58"), 1))
            p.drawText(M + PW // 2 - 45, int(mid) + 4, "All outputs OFF")
            # still draw zero axis
            p.setPen(QPen(QColor("#30363d"), 1))
            p.drawLine(M, int(mid), W, int(mid))
            self._draw_yaxis(p, H, mid, 0.0)
            p.end()
            return

        # ── scale: peak voltage = Vpp/2 of the highest channel ──
        v_peak = max(c.volt / 2.0 for c in active)   # half-amplitude
        amp_h  = (H / 2.0) * 0.82                    # max pixel swing

        # ── time window: 3 cycles of the fastest active channel ──
        ref_freq = max(c.freq for c in active)
        t_span   = 3.0 / ref_freq
        N = 500

        # ── draw waveforms ────────────────────────────────────
        for ch_obj in self._channels:
            color = CH_COLORS[ch_obj.ch]
            if not ch_obj.enabled:
                p.setPen(QPen(QColor(color + "33"), 1, Qt.DashLine))
                p.drawLine(M, int(mid), W, int(mid))
                continue

            p.setPen(QPen(QColor(color), 1.6))
            phase_rad = math.radians(ch_obj.phase)
            # scale this channel's amplitude relative to v_peak
            ch_scale = (ch_obj.volt / 2.0) / v_peak if v_peak > 0 else 1.0

            pts = []
            for i in range(N + 1):
                t     = i / N * t_span
                y_val = math.sin(2 * math.pi * ch_obj.freq * t + phase_rad)
                px = M + int(i / N * PW)
                py = int(mid - y_val * amp_h * ch_scale)
                pts.append((px, py))
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])

        # ── Y-axis overlay (drawn last so it's on top) ────────
        self._draw_yaxis(p, H, mid, v_peak)

        # ── zero line (subtle) ────────────────────────────────
        p.setPen(QPen(QColor("#30363d"), 1))
        p.drawLine(M, int(mid), W, int(mid))

        p.end()

    def _draw_yaxis(self, p, H: int, mid: float, v_peak: float):
        """Draw the Y-axis line, ticks, and voltage labels."""
        from PyQt5.QtGui import QPen, QColor, QFont
        M      = self.Y_MARGIN
        amp_h  = (H / 2.0) * 0.82
        tick_w = 5          # tick mark length into plot area

        # axis spine
        p.setPen(QPen(QColor("#484f58"), 1))
        p.drawLine(M, 0, M, H)

        if v_peak <= 0:
            return

        # ── ticks at ±Vpeak and 0 ────────────────────────────
        ticks = [
            ( v_peak,  f"+{self._nice_voltage(v_peak)}V"),
            ( 0.0,     "0"),
            (-v_peak,  f"−{self._nice_voltage(v_peak)}V"),
        ]
        p.setFont(QFont("Consolas", 8))

        for v_val, label in ticks:
            if v_peak > 0:
                py = int(mid - (v_val / v_peak) * amp_h)
            else:
                py = int(mid)

            # tick mark
            p.setPen(QPen(QColor("#8b949e"), 1))
            p.drawLine(M - tick_w, py, M + tick_w, py)

            # label (right-aligned inside the margin)
            fm    = p.fontMetrics()
            tw    = fm.horizontalAdvance(label)
            lx    = M - tick_w - tw - 3
            ly    = py + fm.ascent() // 2 - 1
            p.setPen(QPen(QColor("#8b949e"), 1))
            p.drawText(max(0, lx), ly, label)

        # ── Vpp annotation (bottom-left of margin) ────────────
        p.setFont(QFont("Consolas", 7))
        vpp_str = f"Vpp={self._nice_voltage(v_peak * 2)}V"
        p.setPen(QPen(QColor("#484f58"), 1))
        fm = p.fontMetrics()
        p.drawText(2, H - fm.descent() - 2, vpp_str)


# ─────────────────────────────────────────────────────────────
#  MODE TABS
# ─────────────────────────────────────────────────────────────
class EROTTab(QWidget):
    run_requested  = pyqtSignal(list, float, float, bool)  # freqs, volt, dwell, summary_only
    stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        info = QLabel(
            "ELECTROROTATION  —  4 channels, 90° phase steps "
            "(CH1: 0°, CH2: 90°, CH3: 180°, CH4: 270°)\n"
            "Sweep through the frequency list; same potential on all channels."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e; font-size:11px; margin-bottom:8px;")
        layout.addWidget(info)

        badge_row = QHBoxLayout()
        for ch, phase in [(1, '0°'), (2, '90°'), (3, '180°'), (4, '270°')]:
            frame = QFrame()
            frame.setStyleSheet(
                f"border:1px solid {CH_COLORS[ch]}22; border-radius:4px;"
            )
            fl = QHBoxLayout(frame)
            fl.setContentsMargins(8, 4, 8, 4)
            fl.addWidget(ch_label(ch))
            fl.addWidget(QLabel(phase))
            badge_row.addWidget(frame)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        grp = QGroupBox("SWEEP PARAMETERS")
        g   = QGridLayout(grp)
        g.addWidget(QLabel("Applied Potential (Vpp):"), 0, 0)
        self.volt_spin = QDoubleSpinBox()
        self.volt_spin.setRange(0.001, 20.0)
        self.volt_spin.setValue(1.0)
        self.volt_spin.setDecimals(3)
        self.volt_spin.setSuffix(' Vpp')
        g.addWidget(self.volt_spin, 0, 1)

        g.addWidget(QLabel("Dwell Time per Step (s):"), 0, 2)
        self.dwell_spin = QDoubleSpinBox()
        self.dwell_spin.setRange(1, 3600)
        self.dwell_spin.setValue(40)
        self.dwell_spin.setDecimals(1)
        self.dwell_spin.setSuffix(' s')
        g.addWidget(self.dwell_spin, 0, 3)
        layout.addWidget(grp)

        self.freq_editor = FreqListEditor()
        layout.addWidget(self.freq_editor)

        opt_row = QHBoxLayout()
        self.chk_summary = QCheckBox("Summary only  (suppress per-command log lines)")
        self.chk_summary.setChecked(False)
        self.chk_summary.setToolTip(
            "When checked, individual SCPI write/query lines are hidden.\n"
            "One summary line per step is always shown."
        )
        self.chk_summary.setStyleSheet("color:#8b949e; font-size:11px;")
        opt_row.addWidget(self.chk_summary)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        btn_row = QHBoxLayout()
        self.btn_run  = QPushButton("▶  Start EROT Sweep")
        self.btn_run.setObjectName("btn_start")
        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.progress_lbl = QLabel("Idle")
        self.progress_lbl.setStyleSheet("color:#8b949e;")
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_stop)
        btn_row.addStretch()
        btn_row.addWidget(self.progress_lbl)
        layout.addLayout(btn_row)
        layout.addStretch()

        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop.clicked.connect(self.stop_requested)

    def _on_run(self):
        freqs = self.freq_editor.get_frequencies()
        if not freqs:
            QMessageBox.warning(self, "EROT", "Please add at least one frequency.")
            return
        self.run_requested.emit(
            freqs,
            self.volt_spin.value(),
            self.dwell_spin.value(),
            self.chk_summary.isChecked()
        )

    def set_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def update_progress(self, step: int, freq: float):
        self.progress_lbl.setText(f"Step {step+1} — measured {freq:.2f} Hz")
        self.progress_lbl.setStyleSheet("color:#3fb950;")

    def on_done(self):
        self.progress_lbl.setText("Sweep complete")
        self.progress_lbl.setStyleSheet("color:#58a6ff;")
        self.set_running(False)


class DEPTab(QWidget):
    apply_requested  = pyqtSignal(float, float)
    output_requested = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        info = QLabel(
            "DIELECTROPHORESIS  —  All 4 channels share identical "
            "frequency, amplitude, and phase (0°).\n"
            "Adjust frequency and potential, then click Apply."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e; font-size:11px; margin-bottom:8px;")
        layout.addWidget(info)

        badge_row = QHBoxLayout()
        for ch in range(1, 5):
            frame = QFrame()
            frame.setStyleSheet(
                f"border:1px solid {CH_COLORS[ch]}22; border-radius:4px;"
            )
            fl = QHBoxLayout(frame)
            fl.setContentsMargins(8, 4, 8, 4)
            fl.addWidget(ch_label(ch))
            fl.addWidget(QLabel("0°"))
            badge_row.addWidget(frame)
        badge_row.addStretch()
        layout.addLayout(badge_row)

        grp = QGroupBox("SIGNAL PARAMETERS")
        g   = QGridLayout(grp)
        g.addWidget(QLabel("Frequency (Hz):"), 0, 0)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.001, 10_000_000)
        self.freq_spin.setValue(1000)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSuffix(' Hz')
        self.freq_spin.setSingleStep(100)
        g.addWidget(self.freq_spin, 0, 1)

        g.addWidget(QLabel("Applied Potential (Vpp):"), 1, 0)
        self.volt_spin = QDoubleSpinBox()
        self.volt_spin.setRange(0.001, 20.0)
        self.volt_spin.setValue(1.0)
        self.volt_spin.setDecimals(3)
        self.volt_spin.setSuffix(' Vpp')
        g.addWidget(self.volt_spin, 1, 1)
        layout.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("▶  Apply DEP Signal")
        btn_apply.setObjectName("btn_start")
        btn_on  = QPushButton("Output ON")
        btn_on.setObjectName("btn_output_on")
        btn_off = QPushButton("Output OFF")
        btn_off.setObjectName("btn_output_off")
        btn_apply.clicked.connect(self._on_apply)
        btn_on.clicked.connect(lambda: self.output_requested.emit(True))
        btn_off.clicked.connect(lambda: self.output_requested.emit(False))
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_on)
        btn_row.addWidget(btn_off)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def _on_apply(self):
        self.apply_requested.emit(self.freq_spin.value(), self.volt_spin.value())


class EORTab(QWidget):
    apply_requested  = pyqtSignal(str, float, float)
    output_requested = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        info = QLabel(
            "ELECTROORIENTATION  —  Activate one pair of opposing "
            "electrodes (1–3 or 2–4).\n"
            "Active pair: 0° and 180°. Inactive pair: output OFF."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e; font-size:11px; margin-bottom:8px;")
        layout.addWidget(info)

        pair_grp = QGroupBox("ELECTRODE PAIR")
        pg = QHBoxLayout(pair_grp)
        self.btn_13 = QPushButton("CH1 — CH3  (0° / 180°)")
        self.btn_24 = QPushButton("CH2 — CH4  (0° / 180°)")
        self.btn_13.setCheckable(True)
        self.btn_24.setCheckable(True)
        self.btn_13.setChecked(True)
        self.btn_13.setStyleSheet(
            f"QPushButton:checked{{background:#1a3a1a;"
            f"border-color:{CH_COLORS[1]};color:{CH_COLORS[1]};}}"
        )
        self.btn_24.setStyleSheet(
            f"QPushButton:checked{{background:#1a1a3a;"
            f"border-color:{CH_COLORS[2]};color:{CH_COLORS[2]};}}"
        )

        def _pick13():
            self.btn_13.setChecked(True)
            self.btn_24.setChecked(False)
        def _pick24():
            self.btn_24.setChecked(True)
            self.btn_13.setChecked(False)
        self.btn_13.clicked.connect(_pick13)
        self.btn_24.clicked.connect(_pick24)
        pg.addWidget(self.btn_13)
        pg.addWidget(self.btn_24)
        pg.addStretch()
        layout.addWidget(pair_grp)

        grp = QGroupBox("SIGNAL PARAMETERS")
        g   = QGridLayout(grp)
        g.addWidget(QLabel("Frequency (Hz):"), 0, 0)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.001, 10_000_000)
        self.freq_spin.setValue(1000)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSuffix(' Hz')
        g.addWidget(self.freq_spin, 0, 1)

        g.addWidget(QLabel("Applied Potential (Vpp):"), 1, 0)
        self.volt_spin = QDoubleSpinBox()
        self.volt_spin.setRange(0.001, 20.0)
        self.volt_spin.setValue(1.0)
        self.volt_spin.setDecimals(3)
        self.volt_spin.setSuffix(' Vpp')
        g.addWidget(self.volt_spin, 1, 1)
        layout.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("▶  Apply EOR Signal")
        btn_apply.setObjectName("btn_start")
        btn_on  = QPushButton("Output ON")
        btn_on.setObjectName("btn_output_on")
        btn_off = QPushButton("Output OFF")
        btn_off.setObjectName("btn_output_off")
        btn_apply.clicked.connect(self._on_apply)
        btn_on.clicked.connect(lambda: self.output_requested.emit(True))
        btn_off.clicked.connect(lambda: self.output_requested.emit(False))
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_on)
        btn_row.addWidget(btn_off)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def _on_apply(self):
        pair = '13' if self.btn_13.isChecked() else '24'
        self.apply_requested.emit(pair, self.freq_spin.value(), self.volt_spin.value())


class ChannelRow(QWidget):
    def __init__(self, ch: int):
        super().__init__()
        self.ch = ch
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.enabled = QCheckBox()
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)
        layout.addWidget(ch_label(ch))

        layout.addWidget(QLabel("Freq:"))
        self.freq = QDoubleSpinBox()
        self.freq.setRange(0.001, 10_000_000)
        self.freq.setValue(1000)
        self.freq.setDecimals(3)
        self.freq.setSuffix(' Hz')
        self.freq.setFixedWidth(140)
        layout.addWidget(self.freq)

        layout.addWidget(QLabel("Amp:"))
        self.volt = QDoubleSpinBox()
        self.volt.setRange(0.001, 20.0)
        self.volt.setValue(1.0)
        self.volt.setDecimals(3)
        self.volt.setSuffix(' Vpp')
        self.volt.setFixedWidth(110)
        layout.addWidget(self.volt)

        layout.addWidget(QLabel("Phase:"))
        self.phase = QDoubleSpinBox()
        self.phase.setRange(-360, 360)
        self.phase.setValue(0)
        self.phase.setDecimals(1)
        self.phase.setSuffix('°')
        self.phase.setFixedWidth(90)
        layout.addWidget(self.phase)
        layout.addStretch()

    def get_config(self) -> dict:
        return {
            'ch':      self.ch,
            'freq':    self.freq.value(),
            'volt':    self.volt.value(),
            'phase':   self.phase.value(),
            'enabled': self.enabled.isChecked(),
        }


class FreeTab(QWidget):
    apply_requested  = pyqtSignal(list)
    output_requested = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        info = QLabel(
            "FREE MODE  —  Configure each channel independently. "
            "Unchecked channels will have their output turned OFF."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e; font-size:11px; margin-bottom:8px;")
        layout.addWidget(info)

        grp = QGroupBox("CHANNEL CONFIGURATION")
        gl  = QVBoxLayout(grp)
        self.rows = []
        for ch in range(1, 5):
            if ch > 1:
                gl.addWidget(hsep())
            row = ChannelRow(ch)
            gl.addWidget(row)
            self.rows.append(row)
        layout.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("▶  Apply to All Channels")
        btn_apply.setObjectName("btn_start")
        btn_on  = QPushButton("All Output ON")
        btn_on.setObjectName("btn_output_on")
        btn_off = QPushButton("All Output OFF")
        btn_off.setObjectName("btn_output_off")
        btn_apply.clicked.connect(self._on_apply)
        btn_on.clicked.connect(lambda: self.output_requested.emit(True))
        btn_off.clicked.connect(lambda: self.output_requested.emit(False))
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_on)
        btn_row.addWidget(btn_off)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

    def _on_apply(self):
        self.apply_requested.emit([row.get_config() for row in self.rows])


# ─────────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, auto_test: bool = False):
        super().__init__()
        self.setWindowTitle("Function Generator Controller  |  DEP / EROT / EOR")
        self.resize(940, 780)

        # ── worker: plain Python object, no QThread ──────────
        # All long-running methods are dispatched via daemon
        # threading.Thread; signals push results back to Qt safely.
        self.worker = InstrumentWorker()

        self._build_ui()
        self._connect_signals()
        self._set_controls_enabled(False)

        if auto_test:
            # slight delay so the window is fully shown first
            QTimer.singleShot(300, lambda: self._on_test_connect(0.0))

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(4)
        root.setContentsMargins(10, 8, 10, 8)

        # ── ZONE 1: connection panel (compact, fixed height) ──
        self.conn_panel = ConnectionPanel()
        # Prevent the connection bar from growing vertically
        self.conn_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self.conn_panel)
        root.addWidget(hsep())

        # ── ZONE 2 + 3: vertical splitter (work area on top, console on bottom) ──
        #   This makes the console height fully user-adjustable by dragging.
        self.vert_splitter = QSplitter(Qt.Vertical)
        self.vert_splitter.setChildrenCollapsible(False)
        self.vert_splitter.setHandleWidth(5)

        # ── 2a: horizontal splitter inside zone 2 ──
        #   Left = virtual instrument panel (test mode only)
        #   Right = method tabs with scroll areas
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(5)

        # Left: virtual instrument panel (hidden by default)
        self.test_panel = TestModePanel(self.worker)
        self.test_panel.setVisible(False)
        self.main_splitter.addWidget(self.test_panel)

        # Right: mode tabs — each tab wraps its content in a QScrollArea
        #   so the controls never clip when the window is small.
        self.tabs = QTabWidget()
        self.tab_erot = EROTTab()
        self.tab_dep  = DEPTab()
        self.tab_eor  = EORTab()
        self.tab_free = FreeTab()

        for tab, label in [
            (self.tab_erot, "  EROT  "),
            (self.tab_dep,  "  DEP   "),
            (self.tab_eor,  "  EOR   "),
            (self.tab_free, "  FREE  "),
        ]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setWidget(tab)
            self.tabs.addTab(scroll, label)

        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.setStretchFactor(0, 0)   # test panel: no stretch until shown
        self.main_splitter.setStretchFactor(1, 1)   # tabs: take all space

        self.vert_splitter.addWidget(self.main_splitter)

        # ── 2b: console in the bottom pane of the vertical splitter ──
        self.console = Console()
        self.vert_splitter.addWidget(self.console)

        # Default split: ~70 % work area, ~30 % console (set after show via resizeEvent)
        self.vert_splitter.setStretchFactor(0, 3)
        self.vert_splitter.setStretchFactor(1, 1)

        root.addWidget(self.vert_splitter, stretch=1)

    # ── signals ──────────────────────────────────────────────
    def _connect_signals(self):
        self.worker.log_signal.connect(self.console.log)
        self.worker.error_signal.connect(self.console.error)
        self.worker.done_signal.connect(self._on_worker_done)
        self.worker.freq_signal.connect(self.tab_erot.update_progress)

        self.conn_panel.connect_clicked.connect(self._on_connect)
        self.conn_panel.disconnect_clicked.connect(self._on_disconnect)
        self.conn_panel.scan_clicked.connect(self._on_scan)
        self.conn_panel.test_clicked.connect(self._on_test_connect)

        self.tab_erot.run_requested.connect(self._run_erot)
        self.tab_erot.stop_requested.connect(self._stop_sweep)
        self.tab_dep.apply_requested.connect(self._run_dep)
        self.tab_dep.output_requested.connect(self.worker.all_output)
        self.tab_eor.apply_requested.connect(self._run_eor)
        self.tab_eor.output_requested.connect(self.worker.all_output)
        self.tab_free.apply_requested.connect(self._run_free)
        self.tab_free.output_requested.connect(self.worker.all_output)

    def _set_controls_enabled(self, enabled: bool):
        self.tabs.setEnabled(enabled)

    # ── connection actions ───────────────────────────────────
    def _on_scan(self):
        resources = self.worker.list_resources()
        if resources:
            self.conn_panel.populate_resources(resources)
            self.console.log(f"[SCAN] Found: {', '.join(resources)}")
        else:
            self.console.log("[SCAN] No VISA resources found.", color='#f7c948')

    def _on_connect(self, addr: str, buf: int, timeout: int):
        ok = self.worker.connect(addr, buf, timeout)
        self.conn_panel.set_connected(ok, test_mode=False)
        self._set_controls_enabled(ok)
        self._hide_test_panel()

    def _on_disconnect(self):
        self.worker.disconnect()
        self.conn_panel.set_connected(False)
        self._set_controls_enabled(False)
        self._hide_test_panel()

    def _on_test_connect(self, error_rate: float):
        ok = self.worker.connect_virtual(error_rate)
        self.conn_panel.set_connected(ok, test_mode=True)
        self._set_controls_enabled(ok)
        # Reveal the virtual instrument panel on the left at a 1:2 ratio
        self.test_panel.setVisible(True)
        total = self.main_splitter.width()
        self.main_splitter.setSizes([total // 3, (total * 2) // 3])
        self.test_panel.start()
        self.console.log(
            "[TEST MODE] Use any mode tab normally — "
            "commands go to the virtual instrument.",
            color='#d2a8ff'
        )

    def _hide_test_panel(self):
        """Collapse the virtual panel and stop its refresh timer."""
        self.test_panel.stop()
        self.test_panel.setVisible(False)
        # Give all horizontal splitter space back to the tabs
        self.main_splitter.setSizes([0, self.main_splitter.width()])

    def resizeEvent(self, event):
        """Keep splitter proportions sensible as the window is resized."""
        super().resizeEvent(event)
        h = self.vert_splitter.height()
        if h > 0:
            # ~72 % work area, ~28 % console
            self.vert_splitter.setSizes([int(h * 0.72), int(h * 0.28)])

    # ── mode runners ─────────────────────────────────────────
    def _run_erot(self, freqs: list, volt: float, dwell: float, summary_only: bool):
        self.tab_erot.set_running(True)
        mode_str = "summary" if summary_only else "verbose"
        self.console.log(
            f"[EROT] Queuing sweep: {len(freqs)} steps, {volt} Vpp, "
            f"{dwell}s dwell  [{mode_str}]"
        )
        self.worker.reset()
        threading.Thread(
            target=self.worker.run_erot,
            args=(freqs, volt, dwell, summary_only),
            daemon=True
        ).start()

    def _stop_sweep(self):
        self.worker.stop()
        self.console.log("[STOP] Stop requested …", color='#f7c948')

    def _run_dep(self, freq: float, volt: float):
        self.worker.reset()
        threading.Thread(
            target=self.worker.run_dep,
            args=(freq, volt),
            daemon=True
        ).start()

    def _run_eor(self, pair: str, freq: float, volt: float):
        self.worker.reset()
        threading.Thread(
            target=self.worker.run_eor,
            args=(pair, freq, volt),
            daemon=True
        ).start()

    def _run_free(self, configs: list):
        self.worker.reset()
        threading.Thread(
            target=self.worker.run_free,
            args=(configs,),
            daemon=True
        ).start()

    # ── mode-aware done handler ──────────────────────────────
    def _on_worker_done(self, mode: str):
        if mode == "erot":
            self.tab_erot.on_done()
        # dep / eor / free: just log; no extra UI state to reset

    # ── cleanup ──────────────────────────────────────────────
    def closeEvent(self, event):
        self.worker.stop()        # ask any running sweep to halt
        self._hide_test_panel()   # stops refresh timer
        self.worker.disconnect()  # turns outputs off, closes VISA/virtual
        event.accept()


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
def main():
    auto_test = '--test' in sys.argv
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setApplicationName("FG Controller")
    window = MainWindow(auto_test=auto_test)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()