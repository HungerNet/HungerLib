from mapres import MapResolver, maps
import logging
from pathlib import Path
from datetime import datetime
from .utils.exceptions import InvalidLevelError

class MessageRouter:
    def __init__(
        self,
        name: str,
        Servers: list,
        log_path: str,

        origin_maps      = [maps.ascii_colors],
        destination_maps = [maps.ascii_colors],
        broadcast_maps   = [maps.mc_colors],
        file_maps        = [maps.strip_colors],
        prefix_maps      = [maps.ascii_colors, maps.time],

        info_prefix  = '<white>[%hh%:%mm%:%ss%] [INFO]: ',
        warn_prefix  = '<yellow>[%hh%:%mm%:%ss%] [WARN]: ',
        error_prefix = '<red>[%hh%:%mm%:%ss%] [ERROR]: ',
    ):
        self.name = name
        self.Servers = Servers

        # default maps per route
        self.origin_maps = origin_maps
        self.destination_maps = destination_maps
        self.broadcast_maps = broadcast_maps
        self.file_maps = file_maps
        self.prefix_maps = prefix_maps

        # prefixes
        self.info_prefix = info_prefix
        self.warn_prefix = warn_prefix
        self.error_prefix = error_prefix

        # resolver
        self.resolver = MapResolver()
        self.res = self.resolver.res

        # file logger
        self.log_path = Path(log_path)
        self.log_path.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self._init_file_logger()

        # custom level registry
        self.custom_levels = {}

        # routing table
        self.ROUTES = {
            'origin': self.origin,
            'destination': self.destination,
            'broadcast': self.broadcast,
            'filelog': self.filelog
        }

        # global buffer toggle
        self.buffer_enabled = False
        self.buffer = []

        self.origin_output = False

    def enableBuffer(self): self.buffer_enabled = True

    def disableBuffer(self): self.buffer_enabled = False

    def toggleBuffer(self): self.buffer_enabled = not self.buffer_enabled

    def clearBuffer(self): self.buffer = []
    
    def flushBuffer(self):
        for msg in self.buffer:
            print(msg)
        self.clearBuffer()


    def registerLevel(self, name, prefix, file_method=None, routes=None):
        lvl = name.lower()
        self.custom_levels[lvl] = {
            'prefix': prefix,
            'file_method': file_method,
            'routes': routes or ['origin', 'filelog']
        }

        def _method(text, **ctx):
            self._route(lvl, text, None, None, ctx)
        setattr(self, lvl, _method)

    def _init_file_logger(self):
        log_file = self.log_path / f'{self.name}_{datetime.now().strftime("%Y-%m-%d")}.log'
        if not self.logger.handlers:
            handler = logging.FileHandler(str(log_file))
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _format(self, text, maps, **ctx):
        return self.res(text, override_maps=maps, **ctx)

    def _merge_maps(self, base, extra):
        maps = list(base)
        if extra:
            maps.extend(extra)
        return maps

    # prefix resolver
    def _resolve_prefix(self, level, ctx):
        lvl = level.lower() if isinstance(level, str) else None

        if lvl == 'info':
            return self.res(self.info_prefix, override_maps=self.prefix_maps)
        if lvl == 'warn':
            return self.res(self.warn_prefix, override_maps=self.prefix_maps)
        if lvl == 'error':
            return self.res(self.error_prefix, override_maps=self.prefix_maps)
        if lvl in self.custom_levels:
            return self.res(self.custom_levels[lvl]['prefix'], override_maps=self.prefix_maps)
        if level is None:
            return ''
        if lvl == 'custom':
            return ctx.get('prefix', '')

        return self.res(level, override_maps=self.prefix_maps)

    # routing engine
    def _route(self, level, text, extra_maps, override_maps, ctx):
        cfg = self.custom_levels.get(level.lower())
        routes = cfg['routes'] if cfg else ['origin', 'filelog']

        for r in routes:
            self.ROUTES[r](text, level=level, extra_maps=extra_maps, override_maps=override_maps, **ctx)

    # file logging
    def _log_file(self, level, msg):
        lvl = level.lower()
        if lvl in self.custom_levels:
            method = self.custom_levels[lvl]['file_method']
            if method:
                getattr(self.logger, method)(msg)
            return

        {
            'info': self.logger.info,
            'warn': self.logger.warning,
            'error': self.logger.error
        }[lvl](msg)

    # routing primitives
    def origin(self, text, level='info', extra_maps=None, override_maps=None, **ctx):
        maps = self._merge_maps(override_maps or self.origin_maps, extra_maps)
        mapped = self._format(text, maps, **ctx)
        prefix = self._resolve_prefix(level, ctx)
        msg = prefix + mapped
        
        # buffer logic
        if self.buffer_enabled:
            self.buffer.append(msg)
        
        # origin output check
        if self.origin_output:
            print(msg)

        return msg

    def destination(self, text, level='info', extra_maps=None, override_maps=None, **ctx):
        maps = self._merge_maps(override_maps or self.destination_maps, extra_maps)
        msg = self._format(text, maps, **ctx)
        for server in self.Servers:
            if hasattr(server, 'bridge'):
                server.bridge.log(msg, level)
        return msg

    def broadcast(self, text, extra_maps=None, override_maps=None, **ctx):
        maps = self._merge_maps(override_maps or self.broadcast_maps, extra_maps)
        msg = self._format(text, maps, **ctx)
        for server in self.Servers:
            if hasattr(server, 'sendBroadcast'):
                server.sendBroadcast(msg)
        return msg

    def filelog(self, text, level='info', extra_maps=None, override_maps=None, **ctx):
        maps = self._merge_maps(override_maps or self.file_maps, extra_maps)
        msg = self._format(text, maps, **ctx)
        self._log_file(level, msg)
        return msg

    # passthrough helpers
    def info(self, text, extra_maps=None, override_maps=None, **ctx):
        self._route('info', text, extra_maps, override_maps, ctx)

    def warn(self, text, extra_maps=None, override_maps=None, **ctx):
        self._route('warn', text, extra_maps, override_maps, ctx)

    def error(self, text, extra_maps=None, override_maps=None, **ctx):
        self._route('error', text, extra_maps, override_maps, ctx)
