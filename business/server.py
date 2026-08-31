import logging
import threading

from easymodbus import modbus_server

from business.runnable import Runnable

# easymodbus stores every data table as a plain 0-indexed Python list of
# length 65535, but it answers a client request for address N out of
# list slot N + 1 (see ModbusServer.__execute_server_request). These
# helpers hide that off-by-one so callers work with the address a Modbus
# client actually sees.
_ADDR_OFFSET = 1


class Server(Runnable):
    def __init__(self, host="127.0.0.1", port=502):
        self.host = host
        self.port = port
        self.server = modbus_server.ModbusServer()
        self.server.host = host
        self.server.port = port
        # Quieten the per-request INFO logging so the prompt stays readable.
        self.server.logging_level = logging.WARNING
        self._thread = None

    # --- lifecycle ---------------------------------------------------------

    def start(self):
        """Start the Modbus server on a background thread and return."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.server.listen, daemon=True)
        self._thread.start()
        print(f"Modbus server listening on {self.host}:{self.port}")

    def run(self):
        """Start the server, then accept register edits from stdin."""
        self.start()
        self._command_loop()

    # --- register access -------------------------------------------------

    def set_holding_register(self, address, value):
        self.server.holding_registers[address + _ADDR_OFFSET] = int(value)

    def set_input_register(self, address, value):
        self.server.input_registers[address + _ADDR_OFFSET] = int(value)

    def set_coil(self, address, value):
        self.server.coils[address + _ADDR_OFFSET] = bool(value)

    def set_discrete_input(self, address, value):
        self.server.discrete_inputs[address + _ADDR_OFFSET] = bool(value)

    def get_holding_register(self, address):
        return self.server.holding_registers[address + _ADDR_OFFSET]

    def get_input_register(self, address):
        return self.server.input_registers[address + _ADDR_OFFSET]

    # --- interactive prompt --------------------------------------------

    _SETTERS = {
        "hr": "set_holding_register",
        "ir": "set_input_register",
        "co": "set_coil",
        "di": "set_discrete_input",
    }

    def _command_loop(self):
        print(
            "Commands:\n"
            "  hr <addr> <value>   set holding register\n"
            "  ir <addr> <value>   set input register\n"
            "  co <addr> <0|1>     set coil\n"
            "  di <addr> <0|1>     set discrete input\n"
            "  get hr|ir <addr>    read a register back\n"
            "  quit"
        )
        try:
            while True:
                try:
                    line = input("> ").strip()
                except EOFError:
                    break
                if not line:
                    continue
                parts = line.split()
                cmd = parts[0].lower()

                if cmd in ("quit", "exit", "q"):
                    break

                try:
                    if cmd == "get" and len(parts) == 3:
                        table, addr = parts[1].lower(), int(parts[2])
                        if table == "hr":
                            print(self.get_holding_register(addr))
                        elif table == "ir":
                            print(self.get_input_register(addr))
                        else:
                            print("unknown table:", table)
                    elif cmd in self._SETTERS and len(parts) == 3:
                        addr, value = int(parts[1]), int(parts[2])
                        getattr(self, self._SETTERS[cmd])(addr, value)
                        print(f"{cmd}[{addr}] = {value}")
                    else:
                        print("bad command")
                except (ValueError, IndexError) as exc:
                    print("error:", exc)
        except KeyboardInterrupt:
            pass
        print("stopping")
