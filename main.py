

import csv
import math
import os
import time
import threading
from datetime import datetime

from flask import Flask, jsonify
from flask_cors import CORS

try:
    import can
except ImportError:
    can = None

app = Flask(__name__)
CORS(app)

# ── CSV log file — new file on every boot ─────────────────────────────────────
def _next_log_filename():
    base = "csv_log"
    ext = ".csv"
    if not os.path.exists(base + ext):
        return base + ext
    index = 1
    while os.path.exists(f"{base}{index}{ext}"):
        index += 1
    return f"{base}{index}{ext}"

CSV_LOG_FILE = _next_log_filename()
print(f"[LOG] Logging CAN data to: {CSV_LOG_FILE}")

# ── Shared state (protected by _lock) ─────────────────────────────────────────
_lock = threading.Lock()
_csv_header_written = False
_logging_enabled    = True        # toggled via /log-toggle
cell_voltages = {}
request_count = 0


def default_values():
    return {
        "rpm": 0,
        "motor_current": 0,
        "output_voltage": 0,
        "pack_current": 0,
        "pack_voltage": 0,
        "state_of_charge": 0,
        "high_temp": 0,
        "low_temp": 0,
        "high_cell_voltage": 0,
        "low_cell_voltage": 0,
        "dcl": 0,
        "ccl": 0,
        "speed": 0,
        "pack_health": 0,
        "relay_state": 0,
    }


latest_values = default_values()


# ── CSV logging ────────────────────────────────────────────────────────────────
def log_can_frame(message):
    global _csv_header_written
    if not _logging_enabled:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    data = message.data
    dlc = len(data)
    bytes_padded = [f"{data[i]:02X}" if i < dlc else "" for i in range(8)]
    with open(CSV_LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not _csv_header_written:
            writer.writerow(["timestamp", "id", "dlc",
                             "data0", "data1", "data2", "data3",
                             "data4", "data5", "data6", "data7"])
            _csv_header_written = True
        writer.writerow([timestamp, f"{message.arbitration_id:X}", dlc] + bytes_padded)

    print(f"[CAN] {timestamp}  ID=0x{message.arbitration_id:03X}  "
          f"DLC={dlc}  Data={' '.join(f'{b:02X}' for b in data)}")


# ── CAN parsing ────────────────────────────────────────────────────────────────
def parse_can_message(message, values):
    global cell_voltages
    data = message.data
    arb_id = message.arbitration_id

    if not data or len(data) == 0:
        return

    # 0x6B0: Relay_State, Pack_kW_Power
    if arb_id == 0x6B0 and len(data) >= 4:
        values["relay_state"] = (data[0] << 8) | data[1]
        values["pack_kw_power"] = ((data[2] << 8) | data[3]) * 0.1

    # 0x6B1: Pack_CCL (bytes 4-5), Pack_Health (byte 6)
    elif arb_id == 0x6B1 and len(data) >= 7:
        values["ccl"] = ((data[4] << 8) | data[5]) * 1.0
        values["pack_health"] = data[6] * 1.0

    # 0x6B2: Pack_Current, Pack_Inst_Voltage, Pack_Open_Voltage, Pack_SOC
    # DBC: Pack_Current : 7|16@0+ (0.1,0) — Motorola, scale 0.1
    # Orion BMS2 encodes current as signed 16-bit (positive=discharge, negative=charge)
    elif arb_id == 0x6B2 and len(data) >= 7:
        raw_current = (data[0] << 8) | data[1]
        if raw_current >= 0x8000:          # two's-complement sign correction
            raw_current -= 0x10000
        values["pack_current"] = raw_current * 0.1
        values["pack_voltage"] = ((data[2] << 8) | data[3]) * 0.1
        values["pack_open_voltage"] = ((data[4] << 8) | data[5]) * 0.1
        values["state_of_charge"] = data[6] * 0.5

    # 0x6B5: High_Temperature (bytes 0-1), Low_Temperature (bytes 2-3)
    # DBC: High_Temperature : 7|16@0+ (1.0,0), Low_Temperature : 23|16@0+ (1.0,0)
    # Both are signed 16-bit (two's-complement) — same pattern as pack current
    elif arb_id == 0x6B5 and len(data) >= 4:
        raw_high = (data[0] << 8) | data[1]
        if raw_high >= 0x8000:
            raw_high -= 0x10000
        raw_low = (data[2] << 8) | data[3]
        if raw_low >= 0x8000:
            raw_low -= 0x10000
        values["high_temp"] = float(raw_high)
        values["low_temp"] = float(raw_low)

    # 0x36: Cell broadcast — track min/max cell voltage
    elif arb_id == 0x36 and len(data) >= 3:
        cell_id = data[0]
        cell_voltage = ((data[1] << 8) | data[2]) * 0.0001
        cell_voltages[cell_id] = cell_voltage
        if cell_voltages:
            values["high_cell_voltage"] = max(cell_voltages.values())
            values["low_cell_voltage"] = min(cell_voltages.values())

    elif arb_id == 0x181:

        regid = data[0]

        if regid == 0x30:          # Motor RPM

            rpm = data[1] | (data[2] << 8)

            if rpm >= 0x8000:
                rpm -= 0x10000

            values["rpm"] = rpm

            values["speed"] = (
                rpm *
                2 * math.pi *
                0.4064 *
                3.6 /
                (60 * 3.5)
            )

        elif regid == 0x27:        # Motor current

            current = data[1] | (data[2] << 8)

            if current >= 0x8000:
                current -= 0x10000

            values["motor_current"] = current

# ── Background CAN reader thread ───────────────────────────────────────────────
def _can_reader_thread():
    """Continuously reads the CAN bus, logs every frame, and updates shared state.
    Runs independently of any HTTP request from display.py."""
    global latest_values

    if can is None:
        print("[CAN] python-can not installed — reader thread exiting.")
        return

    while True:
        if not os.path.exists('/dev/ttyUSB0'):
            print("[CAN] /dev/ttyUSB0 not found — retrying in 5 s …")
            time.sleep(5)
            continue

        bus = None
        try:
            bus = can.interface.Bus(
                channel='/dev/ttyUSB0',
                interface='slcan',
                bitrate=250000,
            )
            print(f"[CAN] Bus opened — logging to {CSV_LOG_FILE}")

            while True:
                message = bus.recv(timeout=1.0)
                if message is None:
                    continue
                log_can_frame(message)
                with _lock:
                    parse_can_message(message, latest_values)

        except can.CanError as exc:
            print(f"[CAN] Error: {exc} — retrying in 5 s …")
            time.sleep(5)
        except Exception as exc:
            print(f"[CAN] Unexpected error: {exc} — retrying in 5 s …")
            time.sleep(5)
        finally:
            if bus:
                try:
                    bus.shutdown()
                except Exception:
                    pass
                print("[CAN] Bus closed.")


# Start the reader as a daemon thread (exits automatically when Flask exits)
_reader = threading.Thread(target=_can_reader_thread, daemon=True, name="can-reader")
_reader.start()


# ── Flask routes ───────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return "Hello Flask!"


@app.route('/values', methods=['GET'])
def get_values():
    global request_count
    with _lock:
        snapshot = dict(latest_values)
        request_count += 1
    snapshot['log_filename'] = CSV_LOG_FILE   # always send current log name
    print(f"[HTTP] Request #{request_count} → {snapshot}")
    return jsonify(snapshot)


@app.route('/new-log', methods=['POST'])
def new_log():
    global CSV_LOG_FILE, _csv_header_written
    _csv_header_written = False
    CSV_LOG_FILE = _next_log_filename()
    print(f"[LOG] Switched to new log file: {CSV_LOG_FILE}")
    return jsonify({"filename": CSV_LOG_FILE})


@app.route('/log-toggle', methods=['POST'])
def log_toggle():
    global _logging_enabled
    _logging_enabled = not _logging_enabled
    state = "on" if _logging_enabled else "off"
    print(f"[LOG] Logging toggled {state}")
    return jsonify({"logging": _logging_enabled})


if __name__ == '__main__':
    # use_reloader=False prevents Flask from spawning a second process
    # (which would start a duplicate CAN reader thread)
    app.run(debug=True, use_reloader=False, threaded=True)
