# #!/usr/bin/env python3
import argparse, asyncio
from business.client.client import Client
from business.server import Server
from business.publish_to_plc import PublishToPLC

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
    args = parser.parse_args(argv)

    print(args.instance, "---")

    instance = factories[args.instance]()
    await instance.run()

if __name__ == "__main__":
    asyncio.run(main())
    print("Done")
