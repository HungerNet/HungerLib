import time
import re

from hungerlib.panel import Panel
from hungerlib.servers import GenericServer
from hungerlib.bridgeclient import BridgeClient
from hungerlib.utils.exceptions import InvalidModeError


class MinecraftServer(GenericServer):
    '''Minecraft Pterodactyl Server'''
    def __init__(
        self,
        name: str,
        panel: Panel,
        server_id: str,
        server_domain: str,
        server_port: int,

        bridge_url: str,
        bridge_token: str,
        history_handler=None,
        newline_handler=None,
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
        self.bridge = BridgeClient(bridge_url, bridge_token, history_handler=history_handler, newline_handler=newline_handler)


    # basic getter methods
    def getBridgeVersion(self) -> str | None:
        return self.bridge.getVersion()

    def getVersion(self) -> str | None:
        return self.bridge.getMinecraftVersion()

    def getPlatform(self) -> str | None:
        return self.bridge.getPlatform()


    def getPlayers(self, mode: str = 'count') -> int | list | None:
        '''Returns current online players'''
        if mode == 'count':
            return self.bridge.getPlayers('count')
        elif mode == 'list':
            return self.bridge.getPlayers('list')
        else:
            raise InvalidModeError(f"Invalid mode: '{mode}'")

    def getMaxPlayers(self) -> int:
        '''
        Runs the 'list' command and extracts the max player count.
        Expected format:
        There are 0 of a max of 20 players online:
        '''
        try:
            output = self.bridge.runCommand('list', show_console=False, silent=False, normalize=True)
        except Exception:
            return 0
        if not output:
            return 0
        # Regex for: "There are X of a max of Y players online"
        match = re.search(r'There are \d+ of a max of (\d+) players online:', output)
        if match:
            return int(match.group(1))
        return 0

    def getTPS(self, mode: str = 'current', rounding: int = 3) -> float | None:
        '''
        Returns TPS values:
        - current:   EMA20
        - 1m:        EMA1200
        - 5m:        EMA6000
        - tick_time: avg tick time (ms)
        '''
        try:
            value = self.bridge.getTPS(mode)
        except InvalidModeError:
            return None
        if value is None:
            return None
        return round(value, rounding) if rounding is not None else value


    # commands
    def sendConsoleCommand(
        self,
        command: str,
        show_console: bool = False,
        silent: bool = False,
        normalize: bool = True
    ):
        '''Runs a Minecraft command with optional output capture'''
        return self.bridge.runCommand(
            command,
            show_console=show_console,
            silent=silent,
            normalize=normalize
        )

    def sendBroadcast(self, message: str):
        '''Sends a broadcast using tellraw'''
        safe = message.replace('"', '\\"')
        cmd = f'tellraw @a {{"text":"{safe}"}}'
        return self.bridge.runCommand(cmd, show_console=True)

    # stream passthrough methods
    def connectStream(self, keepalive: int=15): self.bridge.stream.connect(keepalive)
    def disconnectStream(self): self.bridge.stream.disconnect()
    def isStreamConnected(self): self.bridge.stream.isConnected()
    def getRawStream(self): self.bridge.streamgetRaw()
    def getSanitizedStream(self): self.bridge.stream.getSanitized()
    def getTimestampedStream(self): self.bridge.stream.getTimestamped()
