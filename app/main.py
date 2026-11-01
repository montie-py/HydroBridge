# #!/usr/bin/env python3
import argparse, asyncio, logging
from app.client import Client
from app.server import Server
from app.publish_to_plc import PublishToPLC

# run as `python -m app.main`, so __name__ would be "__main__"; name it to sit under "app"
logger = logging.getLogger("app.main")

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level):
    # The root logger stays at WARNING: easymodbus logs every request/response at INFO
    # straight on the root logger, and the Azure SDK is chatty at INFO too.
    # Our own loggers get the requested level explicitly, so easymodbus changing the
    # root level (ModbusServer.logging_level does) doesn't affect them.
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT)
    for name in ("hydrobridge", "app"):
        logging.getLogger(name).setLevel(level)


class InstanceHandler:
    def get_client(self):
        return Client()

    def get_server(self):
        return Server()

    def get_publish_to_plc(self):
        return PublishToPLC()


async def main(argv=None):
    instance_handler = InstanceHandler()
    factories = {
        "client": instance_handler.get_client,
        "server": instance_handler.get_server,
        "publish_plc": instance_handler.get_publish_to_plc,
    }

    parser = argparse.ArgumentParser(description='HydroBridge: Parsing PLC registers and sending them to Azure')
    parser.add_argument('--instance', choices=factories, default='client')
    parser.add_argument('--log-level', choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO",
                        help="level for HydroBridge's own messages (third-party libraries stay at WARNING)")
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    logger.info("Starting %s", args.instance)

    instance = factories[args.instance]()
    await instance.run()

if __name__ == "__main__":
    asyncio.run(main())
    logger.info("Done")
