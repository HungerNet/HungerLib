import os
import time
from statistics import mean
from hungerlib.panel import Panel
from hungerlib.servers.generic import GenericServer
from hungerlib.servers.minecraft import MinecraftServer


class Snapshot:
    def __init__(
        self,
        Server: 'Server',
        rounding: int = 2,
        duration: float = 0.0,
        interval: float = 0.5,
        drop_outliers: int = 0,
        gb: bool = False,
    ):
        '''
        Takes a snapshot of server resources.
        If duration > 0, performs smoothing by sampling repeatedly.

        duration: total seconds to sample (0 = no smoothing)
        interval: delay between samples
        drop_outliers: number of highest and lowest samples to drop (per metric)
        '''
        self.Server = Server

        # --- sampling mode ---
        if duration > 0:
            samples = {
                'ram': [],
                'cpu': [],
                'network_in': [],
                'network_out': [],
                'tps': [],
                'players': []
            }

            end = time.time() + duration
            while time.time() < end:
                samples['ram'].append(Server.getRAM(rounding, gb))
                samples['cpu'].append(Server.getCPU())
                samples['network_in'].append(Server.getNetworkIn(rounding, gb))
                samples['network_out'].append(Server.getNetworkOut(rounding, gb))
                if hasattr(Server, 'getTPS'):
                    samples['tps'].append(Server.getTPS())
                if hasattr(Server, 'getPlayers'):
                    samples['players'].append(Server.getPlayers())
                time.sleep(interval)

            def smooth(values):
                if not values:
                    return None
                values = sorted(values)
                if drop_outliers > 0:
                    values = values[drop_outliers:len(values) - drop_outliers]
                return mean(values) if values else None

            self.ram = smooth(samples['ram'])
            self.cpu = smooth(samples['cpu'])
            self.network_in = smooth(samples['network_in'])
            self.network_out = smooth(samples['network_out'])
            self.tps = smooth(samples['tps'])
            self.players = Server.getPlayers('count')

        # --- instant snapshot (no smoothing) ---
        else:
            self.ram = Server.getRAM(rounding, gb)
            self.cpu = Server.getCPU()
            self.network_in = Server.getNetworkIn(rounding, gb)
            self.network_out = Server.getNetworkOut(rounding, gb)
            self.tps = Server.getTPS() if hasattr(Server, 'getTPS') else None
            self.players = Server.getPlayers('count')

        # uptime is static
        self.uptime = Server.getUptime()
        self.uptime_formatted = Server.getUptime(True)

    def __str__(self):
        base = (
            f'Server: {self.Server.name}\n'
            f'Uptime: {self.uptime_formatted}\n'
            f'RAM: {self.ram}\n'
            f'CPU: {self.cpu}\n'
            f'Network (in): {self.network_in}\n'
            f'Network (out): {self.network_out}'
        )
        if self.tps is not None:
            base += f'\nTPS: {self.tps}'
        if self.players is not None:
            base += f'\nOnline players: {self.players}'
        return base

def clearTerminal():
    os.system('clear' if os.name == 'posix' else 'cls')

def validateAll(panel: Panel, server: GenericServer | MinecraftServer) -> bool:
    return (
        panel.ping() is True and
        panel.validateAPI() is True and
        server.getStatus() == 'running'
    )