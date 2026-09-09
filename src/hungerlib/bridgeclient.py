import time
import threading
import re
import requests
import hmac
import hashlib
import json
import uuid
from urllib.parse import urlparse
from .utils.exceptions import HungerBridgeError, InvalidLevelError, InvalidModeError


def _canonicalize_json_body(value):
    if value is None:
        return ''
    try:
        return json.dumps(value, separators=(',', ':'), sort_keys=True)
    except Exception:
        return str(value)


def _normalize_path(path: str | None) -> str:
    if not path:
        return '/'
    normalized = str(path).strip()
    if not normalized:
        return '/'
    if '://' in normalized:
        try:
            parsed = urlparse(normalized)
            normalized = parsed.path or '/'
        except Exception:
            normalized = normalized.split('://', 1)[1]
            if '/' in normalized:
                normalized = normalized.split('/', 1)[1]
    normalized = normalized.split('?', 1)[0].split('#', 1)[0]
    if not normalized.startswith('/'):
        normalized = '/' + normalized
    while len(normalized) > 1 and normalized.endswith('/'):
        normalized = normalized[:-1]
    return normalized or '/'


class Stream:
    '''SSE streaming wrapper for /server/stream.'''
    def __init__(self, base_url: str, headers_provider, history_handler=None, new_log_handler=None):
        self.url = base_url.rstrip('/') + '/server/stream'
        self.headers_provider = headers_provider
        self.history_handler = history_handler
        self.new_log_handler = new_log_handler

        self.raw_stream = []
        self.sanitized_stream = []
        self.timestamped_stream = {}

        self._thread = None
        self._stop_event = None
        self._session = None

    def _default_history_handler(self, historic_lines):
        for line in historic_lines:
            clean = self.sanitize(line)
            ts = self.extractTimestamp(clean)
            self.raw_stream.append(line)
            self.sanitized_stream.append(clean)
            if ts is not None:
                self.timestamped_stream[ts] = clean

    def _default_new_log_handler(self, line):
        clean = self.sanitize(line)
        ts = self.extractTimestamp(clean)
        self.raw_stream.append(line)
        self.sanitized_stream.append(clean)
        if ts is not None:
            self.timestamped_stream[ts] = clean

    def connect(self, keepalive: int = 15, history: int | None = None):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event = threading.Event()
        self._session = requests.Session()

        def _build_url_with_history(url: str, history: int | None):
            if not history:
                return url
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}history={history}"

        def _run(history: int | None = None):
            history_phase = True
            history_lines = []
            history_deadline = time.time() + (1.0 if history else keepalive)

            request_url = _build_url_with_history(self.url, history)
            try:
                req_headers = self.headers_provider() if callable(self.headers_provider) else self.headers_provider
                with self._session.get(request_url, headers=req_headers, stream=True) as r:
                    if not r.ok:
                        raise requests.HTTPError(f'{r.status_code}: {r.text}')
                    for raw in r.iter_lines(decode_unicode=True):
                        if self._stop_event.is_set():
                            break
                        if not raw or not raw.startswith('data:'):
                            continue

                        line = raw[len('data:'):].lstrip()
                        if history_phase:
                            history_lines.append(line)
                            if time.time() >= history_deadline:
                                try:
                                    (self.history_handler or self._default_history_handler)(history_lines)
                                except Exception:
                                    pass
                                history_phase = False
                            continue

                        try:
                            (self.new_log_handler or self._default_new_log_handler)(line)
                        except Exception:
                            pass
            except Exception:
                pass
            finally:
                if self._session:
                    try:
                        self._session.close()
                    except Exception:
                        pass
                self._thread = None
                self._session = None
                self._stop_event = None

        self._thread = threading.Thread(target=_run, kwargs={"history": history}, name='HungerBridgeStream', daemon=True)
        self._thread.start()

    def disconnect(self):
        if self._stop_event:
            self._stop_event.set()
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        self._thread = None
        self._session = None
        self._stop_event = None

    def isConnected(self) -> bool: return self._thread is not None and self._thread.is_alive()
    def getRaw(self) -> list: return list(self.raw_stream)
    def getSanitized(self) -> list: return list(self.sanitized_stream)
    def getTimestamped(self) -> dict: return dict(self.timestamped_stream)

    @staticmethod
    def sanitize(line: str) -> str:
        ansi_re = re.compile(r'\x1b\[[0-9;]*m')
        clean = ansi_re.sub('', line)
        clean = clean.replace('\\n', '\n').replace('\\r', '\r')
        return clean.rstrip()

    @staticmethod
    def extractTimestamp(line: str) -> str | None:
        m = re.match(r'\[([0-9]{2}:[0-9]{2}:[0-9]{2})\]', line)
        return m.group(1) if m else None


class BridgeClient:
    def __init__(self, url: str, token_id: str | None = None, token_secret: str | None = None, history_handler=None, new_log_handler=None):
        self.base = url.rstrip('/')
        self._token_id = token_id
        self._token_secret = token_secret

        self._static_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

        header_provider = (lambda: self._build_auth_headers('GET', '/server/stream', None)) if (self._token_id and self._token_secret) else dict(self._static_headers)

        self.stream = Stream(base_url=self.base, headers_provider=header_provider, history_handler=history_handler, new_log_handler=new_log_handler)

    # http helpers
    def _post(self, path: str, payload):
        full_path = '/' + path.lstrip('/')
        body_str = _canonicalize_json_body(payload)
        headers = self._build_auth_headers('POST', full_path, payload)
        r = requests.post(self.base + full_path, headers=headers, data=body_str)
        if not r.ok:
            raise HungerBridgeError(f'HungerBridge error {r.status_code}: {r.text}')
        try:
            return r.json()
        except Exception:
            return r.text

    def _get(self, path: str):
        full_path = '/' + path.lstrip('/')
        headers = self._build_auth_headers('GET', full_path, None)
        r = requests.get(self.base + full_path, headers=headers)
        if not r.ok:
            raise HungerBridgeError(f'HungerBridge error {r.status_code}: {r.text}')
        try:
            return r.json()
        except Exception:
            return r.text

    def _build_auth_headers(self, method: str, path: str, body):
        headers = dict(self._static_headers)
        if self._token_secret and self._token_id:
            timestamp = str(int(time.time()))
            nonce = uuid.uuid4().hex
            normalized_path = _normalize_path(path)
            body_str = '' if body is None else _canonicalize_json_body(body)
            msg = f"{method.upper()}\n{normalized_path}\n{timestamp}\n{nonce}\n{body_str}"
            try:
                key_bytes = bytes.fromhex(self._token_secret)
            except Exception:
                key_bytes = self._token_secret.encode('utf-8')
            sig = hmac.new(key_bytes, msg.encode('utf-8'), hashlib.sha256).hexdigest()
            headers.update({'X-Auth-Id': self._token_id, 'X-Auth-Timestamp': timestamp, 'X-Auth-Nonce': nonce, 'X-Auth-Signature': sig})
        return headers

    def _extract(self, response, path: str):
        '''Extract a dot-path from a dict response. Returns None if missing.'''
        if response is None:
            return None
        if path is None or path == '':
            return response
        parts = path.split('.')
        cur = response
        for p in parts:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    # --- Actions (return full dicts unless runCommand normalize=True) ------------------
    def ping(self):
        '''Return full /ping response dict.'''
        return self._get('ping')

    def getPing(self) -> int:
        '''Round-trip latency (ms) measured client-side.'''
        start = time.time()
        self._get('ping')
        end = time.time()
        return int((end - start) * 1000)

    def runCommand(self, command: str, showConsole: bool = False, silent: bool = False, normalize: bool = True):
        '''POST /server/run. If normalize=False returns full dict; otherwise returns normalized string or None.'''
        resp = self._post('server/run', {'command': command, 'silent': silent, 'show_console': showConsole})
        if not normalize:
            return resp
        # normalize output to string when possible
        if isinstance(resp, dict):
            out = resp.get('output')
            if isinstance(out, list):
                return '\n'.join(str(x) for x in out)
            if isinstance(out, (str, bytes)):
                return out
            return None
        if isinstance(resp, list):
            return '\n'.join(str(x) for x in resp)
        if isinstance(resp, (str, bytes)):
            return resp
        return None

    def stopServer(self):
        '''POST /server/stop — returns full server response dict.'''
        return self._post('server/stop', {})

    def restartServer(self):
        '''POST /server/restart — returns full server response dict.'''
        return self._post('server/restart', {})

    def log(self, message: str, level: str = 'info'):
        '''POST /server/log — preserve original semantics and return full dict.
        If level is None, apply the backspace trick to avoid explicit level.
        '''
        valid_levels = ['info', 'warn', 'error', None]
        if level not in valid_levels:
            raise InvalidLevelError(f"'{level}' is not a valid log level")
        if level is not None:
            return self._post('server/log', {'level': level, 'message': message})
        no_level_message = ('\b' * 50) + message
        return self._post('server/log', {'level': 'info', 'message': no_level_message})

    def streamLogs(self) -> Stream:
        return self.stream

    # --- Auth & Server metadata ------------------------------------------------------
    def authCheck(self, field: str | None = None):
        resp = self._get('auth/check')
        if field is None:
            return resp
        return self._extract(resp, field)

    def serverMeta(self, field: str | None = None):
        resp = self._get('server/meta')
        if field is None:
            return resp
        return self._extract(resp, field)

    def serverStatus(self):
        return self._extract(self.ping(), 'ok')

    def getBridgeVersion(self) -> str | None:
        return self.serverMeta('bridge_version')

    def getPlatform(self) -> str | None:
        return self.serverMeta('platform').title()

    def getMinecraftVersion(self) -> str | None:
        return self.serverMeta('minecraft_version')

    # --- Players ---------------------------------------------------------------------
    def getPlayers(self, field: str | None = None):
        resp = self._get('players/list')
        if field is None:
            return resp
        return self._extract(resp, field)

    # --- World -----------------------------------------------------------------------
    def getTPS(self, mode: str = 'current'):
        resp = self._get('world/tps')
        if mode == 'current':
            return self._extract(resp, 'tps')
        if mode == '1m':
            return self._extract(resp, 'tps_1m')
        if mode == '5m':
            return self._extract(resp, 'tps_5m')
        if mode == 'tick_time':
            return self._extract(resp, 'tick_time_ms')
        raise InvalidModeError(f"Invalid mode: '{mode}'")

    def getMSPT(self, field: str | None = None):
        resp = self._get('world/mspt')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getLoadedChunks(self, field: str | None = None):
        resp = self._get('world/chunks')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getWorldTime(self, field: str | None = None):
        resp = self._get('world/time')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getWorldWeather(self, field: str | None = None):
        resp = self._get('world/weather')
        if field is None:
            return resp
        return self._extract(resp, field)

    # --- System ----------------------------------------------------------------------
    def getSystemUptime(self, field: str | None = None):
        resp = self._get('system/uptime')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getSystemCpu(self, field: str | None = None):
        resp = self._get('system/cpu')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getSystemMemory(self, field: str | None = None):
        resp = self._get('system/memory')
        if field is None:
            return resp
        return self._extract(resp, field)

    def getSystemDisk(self, field: str | None = None):
        resp = self._get('system/disk')
        if field is None:
            return resp
        return self._extract(resp, field)

