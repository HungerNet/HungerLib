import time
import re

from hungerlib.panel import Panel
from hungerlib.servers import GenericServer
from hungerlib.bridgeclient import BridgeClient
from hungerlib.utils.exceptions import InvalidModeError
from hungerlib.bridgeclient import BridgeClient

from hungerlib.utils.methods import methods as m


class MinecraftServer(GenericServer):
    '''Minecraft Pterodactyl Server'''
    def __init__(
        self,
        name: str,
        panel: Panel,
        server_id: str,
        server_domain: str,
        server_port: int,

        bridge: BridgeClient,
    ):
        super().__init__(
            name,
            panel,
            server_id,
        )

        # Minecraft-specific fields
        self.server_domain = server_domain
        self.server_port = server_port

        # HungerBridge client
        self.bridge = bridge

        # Proxy methods from bridge client
        m.proxy(self, bridge.isOk)

        m.proxy(self, bridge.getServerTime)
        m.proxy(self, bridge.getPing)

        m.proxy(self, bridge.getTokenInfo)

        m.proxy(self, bridge.getServerMeta)
        m.proxy(self, bridge.getMemoryStats)
        m.proxy(self, bridge.getPlatform)
        m.proxy(self, bridge.getMinecraftVersion)
        m.proxy(self, bridge.getBridgeVersion)
        m.proxy(self, bridge.getBridgePort)

        m.proxy(self, bridge.getPlayers)
        m.proxy(self, bridge.getMaxPlayers)

        m.proxy(self, bridge.getTPS)
        m.proxy(self, bridge.getLoadedChunks)
        m.proxy(self, bridge.getWorldTime)
        m.proxy(self, bridge.getWorldWeather)

        m.proxy(self, bridge.getSystemUptime)
        m.proxy(self, bridge.getCPUStats)
        m.proxy(self, bridge.getMemoryStats)
        m.proxy(self, bridge.getDiskStats)

        m.proxy(self, bridge.log)
        m.proxy(self, bridge.runCommand)

        m.proxy(self, bridge.stopServer)
        m.proxy(self, bridge.restartServer)


        # Proxy BridgeClient's stream
        self.stream = bridge.stream

        # Rename GenericServer methods
        m.rename(self.getRAM, 'getContainerRAM')
        m.rename(self.getCPU, 'getContainerCPU')
        m.rename(self.getDisk, 'getContainerDisk')

        m.rename(self.getUptime, 'getContainerUptime')
        m.rename(self.getStatus, 'getContainerStatus')

        m.rename(self.isOnline, 'isContainerOnline')
        m.rename(self.isOffline, 'isContainerOffline')

        m.rename(self.start, 'startContainer')
        m.rename(self.restart, 'restartContainer')
        m.rename(self.stop, 'stopContainer')
        m.rename(self.kill, 'killContainer')    
