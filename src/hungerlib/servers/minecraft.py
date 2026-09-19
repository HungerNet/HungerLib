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
        m.proxy(bridge.isOk)

        m.proxy(bridge.getServerTime)
        m.proxy(bridge.getPing)

        m.proxy(bridge.getTokenInfo)

        m.proxy(bridge.getServerMeta)
        m.proxy(bridge.getPlatform)
        m.proxy(bridge.getMinecraftVersion)
        m.proxy(bridge.getBridgeVersion)
        m.proxy(bridge.getBridgePort)

        m.proxy(bridge.getPlayers)
        m.proxy(bridge.getMaxPlayers)

        m.proxy(bridge.getTPS)
        m.proxy(bridge.getMSPT)
        m.proxy(bridge.getWorldTime)
        m.proxy(bridge.getWorldWeather)

        m.proxy(bridge.getLoadedChunks)
        m.proxy(bridge.getLoadedEntities)

        m.proxy(bridge.getUptime)
        m.proxy(bridge.getCPUStats)
        m.proxy(bridge.getMemoryStats)
        m.proxy(bridge.getProcessMemory)
        m.proxy(bridge.getGCStats)
        m.proxy(bridge.getThreadStats)
        m.proxy(bridge.getNetworkStats)

        m.proxy(bridge.log)
        m.proxy(bridge.runCommand)
        m.proxy(bridge.broadcast)

        m.proxy(bridge.stopServer)

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
