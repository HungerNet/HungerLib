# Universal server class
from hungerlib.panel import Panel


class GenericServer:
    '''Generic Pterodactyl Server'''
    def __init__(
        self,
        name: str,
        panel: Panel,
        server_id: str,
    ):
        self.name = name
        self.panel = panel
        self.server_id = server_id

        self._cached_resources = None

    # resource and status
    def refresh(self) -> dict:
        '''Forces refetch of resources, caches, then returns them'''
        r = self.panel.get(f'/api/client/servers/{self.server_id}/resources')
        self._cached_resources = r.json().get('attributes', {}).get('resources', {})
        return self._cached_resources

    def resources(self) -> dict:
        '''Returns cached resources'''
        return self._cached_resources or self.refresh()

    def getRAM(self, rounding: int = 2, gb: bool = False) -> float | None:
        '''Returns current RAM usage'''
        mem = self.resources().get('memory_bytes')
        if mem is None:
            return None
        div = 1024 * 1024 * (1024 if gb else 1)
        return round(mem / div, rounding)

    def getCPU(self, rounding: int = 2) -> float | None:
        '''Returns current CPU usage'''
        cpu = self.resources().get('cpu_absolute')
        return round(cpu, rounding) if cpu is not None else None

    def getDisk(self, rounding: int = 2, gb: bool = False) -> float | None:
        '''Returns current disk usage'''
        disk = self.resources().get('disk_bytes')
        if disk is None:
            return None
        div = 1024 * 1024 * (1024 if gb else 1)
        return round(disk / div, rounding)

    def getNetworkIn(self, rounding: int = 2, gb: bool = False) -> float | None:
        '''Returns current network usage'''
        rx = self.resources().get('network_rx_bytes')
        if rx is None:
            return None
        div = 1024 * 1024 * (1024 if gb else 1)
        return round(rx / div, rounding)

    def getNetworkOut(self, rounding: int = 2, gb: bool = False) -> float | None:
        '''Returns current network usage'''
        tx = self.resources().get('network_tx_bytes')
        if tx is None:
            return None
        div = 1024 * 1024 * (1024 if gb else 1)
        return round(tx / div, rounding)

    def getUptime(self, formatted: bool = False) -> int | str | None:
        '''Returns current uptime. Use formatted=True for pretty-print'''
        uptime = self.resources().get('uptime')
        if uptime is None:
            return None
        if not formatted:
            # return seconds # returns seconds
            return uptime # returns miliseconds
        seconds = uptime // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f'{hours}h {minutes}m'
        elif minutes > 0:
            return f'{minutes}m {secs}s'
        else:
            return f'{secs}s'

    def getStatus(self) -> str:
        '''Returns the server's current status'''
        r = self.panel.get(f'/api/client/servers/{self.server_id}/resources')
        return r.json().get('attributes', {}).get('current_state')


    # state helpers
    def isOnline(self) -> bool:
        '''Returns True if online, False if offline'''
        return self.getStatus() == 'running'

    def isOffline(self) -> bool:
        '''Returns True if offline, False if online'''
        return self.getStatus() == 'offline'


    # power actions
    def powerAction(self, action: str) -> tuple:
        '''
        Executes a power action on the server. Valid actions:
        - start
        - restart
        - stop
        - kill
        '''
        valid = {'start', 'restart', 'stop', 'kill'}
        if action not in valid:
            raise ValueError(f'Invalid power action "{action}"')
        payload = {'signal': action}
        r = self.panel.post(f'/api/client/servers/{self.server_id}/power', json=payload)
        return r.status_code, r.text

    def start(self) -> tuple:
        '''Start power action shortcut'''
        return self.powerAction('start')
    def restart(self) -> tuple:
        '''Restart power action shortcut'''
        return self.powerAction('restart')
    def stop(self) -> tuple:
        '''Stop power action shortcut'''
        return self.powerAction('stop')
    def kill(self) -> tuple:
        '''Kill power action shortcut'''
        return self.powerAction('kill')


    # file manager
    def listFiles(self, directory: str = '/'):
        return self.panel.files.list(self.server_id, directory)

    def downloadFile(self, path: str):
        return self.panel.files.download(self.server_id, path)

    def uploadFile(self, directory: str, file_data: str):
        return self.panel.files.upload(self.server_id, directory, file_data)

    def deleteFiles(self, root: str, files: str):
        return self.panel.files.delete(self.server_id, root, files)

    def renameFiles(self, root: str, files: str):
        return self.panel.files.rename(self.server_id, root, files)

    def copyFiles(self, root: str, files: str):
        return self.panel.files.copy(self.server_id, root, files)

    def moveFiles(self, root: str, files: str):
        return self.panel.files.move(self.server_id, root, files)

    def createFolder(self, directory: str, name: str):
        return self.panel.files.create_folder(self.server_id, directory, name)

    def compress(self, root: str, files: str):
        return self.panel.files.compress(self.server_id, root, files)

    def decompress(self, file_path: str):
        return self.panel.files.decompress(self.server_id, file_path)



    # backup manager
    def listBackups(self):
        return self.panel.backups.list(self.server_id)

    def createBackup(self, name: str):
        return self.panel.backups.create(self.server_id, name)

    def deleteBackup(self, backup_id: int):
        return self.panel.backups.delete(self.server_id, backup_id)

    def downloadBackup(self, backup_id: int):
        return self.panel.backups.download(self.server_id, backup_id)


    # database manager
    def listDatabases(self):
        return self.panel.databases.list(self.server_id)

    def createDatabase(self, name: str, remote: str = '%', host: None = None):
        return self.panel.databases.create(self.server_id, name, remote, host)

    def rotateDatabasePassword(self, db_id: str):
        return self.panel.databases.rotate_password(self.server_id, db_id)

    def deleteDatabase(self, db_id: str):
        return self.panel.databases.delete(self.server_id, db_id)


    # startup variables
    def getStartupVariables(self):
        return self.panel.startup.list(self.server_id)
    def updateStartupVariable(self, key: str, value: str):
        return self.panel.startup.update(self.server_id, key, value)


    # schedules
    def listSchedules(self):
        return self.panel.schedules.list(self.server_id)

    def createSchedule(self, payload: dict):
        return self.panel.schedules.create(self.server_id, payload)

    def updateSchedule(self, schedule_id: str, payload: dict):
        return self.panel.schedules.update(self.server_id, schedule_id, payload)

    def deleteSchedule(self, schedule_id: str):
        return self.panel.schedules.delete(self.server_id, schedule_id)

    def runSchedule(self, schedule_id: str):
        return self.panel.schedules.run(self.server_id, schedule_id)


    def enableSchedule(self, schedule_id: str):
        payload = {'is_active': True}
        return self.updateSchedule(schedule_id, payload)

    def disableSchedule(self, schedule_id: str):
        payload = {'is_active': False}
        return self.updateSchedule(schedule_id, payload)


    def getSchedule(self, schedule_id: int) -> dict | None:
        resp = self.panel.schedules.list(self.server_id)
        data = resp.json()
        for item in data.get('data', []):
            attr = item.get('attributes', {})
            if attr.get('id') == schedule_id:
                return {
                    'id': attr.get('id'),
                    'name': attr.get('name'),
                    'description': attr.get('description'),
                    'is_active': attr.get('is_active'),
                    'cron': attr.get('cron'),
                    'minute': attr.get('cron', {}).get('minute'),
                    'hour': attr.get('cron', {}).get('hour'),
                    'day_of_month': attr.get('cron', {}).get('day_of_month'),
                    'month': attr.get('cron', {}).get('month'),
                    'day_of_week': attr.get('cron', {}).get('day_of_week'),
                    'next_run_at': attr.get('next_run_at'),
                    'last_run_at': attr.get('last_run_at'),
                    'only_when_online': attr.get('only_when_online'),
                    'is_processing': attr.get('is_processing'),
                    'created_at': attr.get('created_at'),
                    'updated_at': attr.get('updated_at'),
                    'tasks': attr.get('relationships', {}).get('tasks', {}).get('data', [])
                }
        return None
