from pymodbus.client import ModbusTcpClient
import csv
import time
import threading

client = ModbusTcpClient("127.0.0.1", port=1502)
csv_output_list = []

pause_event = threading.Event()

def csv_writer_loop():
    while True:
        time.sleep(30)
        if not csv_output_list:
            continue

        pause_event.set()

        with open("output.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_output_list)
        print("CSV written with", len(csv_output_list), "rows")
        csv_output_list.clear()

        pause_event.clear()

def polling_loop():
    while True:
        if pause_event.is_set():
            time.sleep(0.1)
            continue
        try:
            if not client.connected:
                client.connect()
            result = client.read_holding_registers(0, count=50)
            if not result.isError():
                csv_output_list.append(result.registers)
            else:
                print("Read error:", result)
            time.sleep(5)

        except Exception as e:
            print("Exception: ", e)

threading.Thread(target=polling_loop, daemon=True).start()
threading.Thread(target=csv_writer_loop, daemon=True).start()

while True:
    time.sleep(1)