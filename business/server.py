from business.runnable import Runnable
from easymodbus import modbus_server
import time


class Server(Runnable):
    def run(self):
        server = modbus_server.ModbusServer()
        server.listen()

        try:
            while True:
                # data stores are plain Python lists, 0-indexed, length 65535
                server.holdingRegisters.localHoldingRegisters[1] = 4711
                server.inputRegisters.localInputRegisters[1] = 2500
                server.coils.localCoils[1] = True
                server.discreteInputs.localDiscreteInputs[1] = True

                # read what a client wrote
                print(server.holdingRegisters.localHoldingRegisters[10])

                time.sleep(1)
        except KeyboardInterrupt:
            server.close()
