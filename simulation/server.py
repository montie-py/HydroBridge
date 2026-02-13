import csv
import time, datetime
import os
import struct
import threading
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusServerContext, ModbusDeviceContext
from pymodbus.datastore import ModbusSequentialDataBlock


# ---------------------------------------------------------
# Correct datastore for pymodbus 3.x
# ---------------------------------------------------------
store = ModbusDeviceContext(
    di=ModbusSequentialDataBlock(0, [0] * 100),  # discrete inputs (FC02)
    co= ModbusSequentialDataBlock(0, [0] * 100),  # coils (FC01)
    ir= ModbusSequentialDataBlock(0, [0] * 100),  # input registers (FC04)
    hr= ModbusSequentialDataBlock(0, [0] * 100),  # holding registers (FC03)
)

context = ModbusServerContext(
    devices=store,
    single=True
)


# ---------------------------------------------------------
# Value encoders
# ---------------------------------------------------------
def treat_date(value: str, values: list) -> None:
    dt = datetime.datetime.strptime(value, "%Y/%m/%d")
    ts = int(time.mktime(dt.timetuple()))
    hi = (ts >> 16) & 0xFFFF
    lo = ts & 0xFFFF
    values.extend([hi, lo])


def treat_time(value: str, values: list) -> None:
    t = datetime.datetime.strptime(value, "%H:%M:%S").time()
    today = datetime.date.today()
    dt = datetime.datetime.combine(today, t)
    ts = int(time.mktime(dt.timetuple()))
    hi = (ts >> 16) & 0xFFFF
    lo = ts & 0xFFFF
    values.extend([hi, lo])


def treat_float(value: str, values: list) -> None:
    float_value = float(value)
    packed = struct.pack(">f", float_value)
    hi, lo = struct.unpack(">HH", packed)
    values.extend([hi, lo])


def treat_int(value: str, values: list) -> None:
    int_value = int(value)
    values.append(int_value)


# ---------------------------------------------------------
# CSV → Modbus register feeder
# ---------------------------------------------------------
def feed_csv_to_registers(cont, csv_p):
    with open(csv_p, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for row in reader:
            values = []

            for value in row:
                if "/" in value:
                    treat_date(value, values)
                elif ":" in value:
                    treat_time(value, values)
                elif "." in value:
                    treat_float(value, values)
                else:
                    treat_int(value, values)

            # Write to holding registers
            cont[0].setValues(3, 0, values)

            print("Updated registers:", values)
            time.sleep(5)


# ---------------------------------------------------------
# Start background thread + Modbus server
# ---------------------------------------------------------
base = os.path.dirname(__file__)
csv_path = os.path.join(base, "..", "input.csv")
csv_path = os.path.abspath(csv_path)

threading.Thread(
    target=feed_csv_to_registers,
    args=(context, csv_path),
    daemon=True
).start()

StartTcpServer(context, address=("0.0.0.0", 1502))
