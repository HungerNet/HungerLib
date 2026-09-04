import time
import threading
import re
import requests
import hmac
import hashlib
import json
import uuid
from .utils.exceptions import HungerBridgeError, InvalidLevelError, InvalidModeError


class Stream:
    '''Streaming wrapper for HungerBridge /stream/logs SSE endpoint.'''
    def __init__(
        self,
        base_url: str,
        # headers may be a dict or a callable returning a dict for dynamic
        # per-connection headers (useful for HMAC-signed SSE connections).
        headers,
        history_handler=None,
        new_log_handler=None
    ):
        self.url = base_url.rstrip('/') + '/stream/logs'
        self.headers = headers

        self.history_handler = history_handler or self._default_history_handler
        self.new_log_handler = new_log_handler or self._default_new_log_handler

        self.raw_stream = []
        self.sanitized_stream = []
        self.timestamped_stream = {}

        self._thread = None
        self._stop_event = None
        self._session = None

    def _default_history_handler(self, historic_lines: list):
        for line in historic_lines:
            clean = self.sanitize(line)
            ts = self.extractTimestamp(clean)
            self.raw_stream.append(line)
            self.sanitized_stream.append(clean)
            if ts is not None:
                self.timestamped_stream[ts] = clean

    def _default_new_log_handler(self, line: str):
        clean = self.sanitize(line)
        ts = self.extractTimestamp(clean)
        self.raw_stream.append(line)
        self.sanitized_stream.append(clean)
        if ts is not None:
            self.timestamped_stream[ts] = clean

    def connect(self, keepalive: int = 15, history: int | None = None):
        '''
        Connect to the SSE stream. Optionally request recent history lines by
        passing `history=<n>` which will add the query parameter `?history=n`.
        '''
        def _build_url_with_history(url: str, history: int | None):
            if not history:
                return url
            sep = '&' if '?' in url else '?'
            return f"{url}{sep}history={history}"

        if self._thread and self._thread.is_alive():
            return

        self._stop_event = threading.Event()
        self._session = requests.Session()

        def _run(history: int | None = None):
            history_phase = True
            history_lines = []
            # If the client explicitly requested history, use a short collection
            # window so the historic lines are dispatched quickly. Otherwise use
            # the provided keepalive timeout.
            history_deadline = time.time() + (1.0 if history else keepalive)

            request_url = _build_url_with_history(self.url, history)
            try:
                # allow headers to be a callable so the client can provide
                # fresh signed headers at connect time
                req_headers = self.headers() if callable(self.headers) else self.headers
                with self._session.get(
                    request_url,
                    headers=req_headers,
                    stream=True
                ) as r:
                    if not r.ok:
                        # raise in a background thread would be silent to callers; log and stop
                        print(f'HungerBridge error {r.status_code}: {r.text}', file=getattr(__import__('sys'), 'stderr'))
                        return

                    for raw in r.iter_lines(decode_unicode=True):
                        if self._stop_event.is_set():
                            break
                        if not raw:
                            continue
                        if not raw.startswith('data:'):
                            continue

                        line = raw[len('data:'):].lstrip()

                        if history_phase:
                            history_lines.append(line)
                            if time.time() >= history_deadline:
                                try:
                                    self.history_handler(history_lines)
                                except Exception:
                                    pass
                                history_phase = False
                            continue

                        try:
                            self.new_log_handler(line)
                        except Exception:
                            pass

            except Exception as e:
                # Avoid raising inside the background thread (silent). Log instead and stop.
                try:
                    import sys
                    print(f'Log stream failed: {e}', file=sys.stderr)
                except Exception:
                    pass
                return
            finally:
                if self._session:
                    try:
                        self._session.close()
                    except Exception:
                        pass
                self._thread = None
                self._session = None
                self._stop_event = None

        self._thread = threading.Thread(
            target=_run,
            kwargs={"history": history},
            name='HungerBridgeStream',
            daemon=True
        )
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
        # remove ANSI sequences, unescape server-escaped newlines, and strip
        clean = ansi_re.sub('', line)
        clean = clean.replace('\\n', '\n').replace('\\r', '\r')
        return clean.rstrip()

    @staticmethod
    def extractTimestamp(line: str):
        m = re.match(r'\[([0-9]{2}:[0-9]{2}:[0-9]{2})\]', line)
        if not m:
            return None
        return m.group(1)


class BridgeClient:
    '''Python client for the HungerBridge API with optional HMAC-signed tokens.'''
    def __init__(
        self,
        url: str,
        token_id: str | None = None,
        token_secret: str | None = None,
        history_handler=None,
        new_log_handler=None
    ):
        self.base = url.rstrip('/')

        # HKIM-only: explicit token_id + token_secret
        self._token_id = token_id
        self._token_secret = token_secret

        self._static_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # If token is provided, use HMAC-signed headers for SSE
        if self._token_id and self._token_secret:
            header_provider = lambda: self._build_auth_headers('GET', '/stream/logs', None)
        else:
            header_provider = dict(self._static_headers)

        self.stream = Stream(
            base_url=self.base,
            headers=header_provider,
            history_handler=history_handler,
            new_log_handler=new_log_handler
        )

    # internal helpers
    def _post(self, path: str, payload):
        full_path = '/' + path
        headers = self._build_auth_headers('POST', full_path, payload)
        r = requests.post(self.base + '/' + path, headers=headers, json=payload)
        if not r.ok:
            raise HungerBridgeError(f'HungerBridge error {r.status_code}: {r.text}')
        try:
            return r.json()
        except Exception:
            return r.text

    def _get(self, path: str):
        full_path = '/' + path
        headers = self._build_auth_headers('GET', full_path, None)
        r = requests.get(self.base + '/' + path, headers=headers)
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

            body_str = ''
            if body is not None:
                try:
                    body_str = json.dumps(body, separators=(',', ':'), sort_keys=True)
                except Exception:
                    body_str = str(body)

            msg = f"{method.upper()}\n{path}\n{timestamp}\n{nonce}\n{body_str}"
            sig = hmac.new(self._token_secret.encode('utf-8'), msg.encode('utf-8'), hashlib.sha256).hexdigest()

            headers.update({
                'X-Auth-Token-Id': self._token_id,
                'X-Auth-Timestamp': timestamp,
                'X-Auth-Nonce': nonce,
                'X-Auth-Signature': sig,
            })
        return headers

    # helper for debugging: return headers used for connecting to the stream
    def get_stream_headers(self) -> dict:
        '''Return the headers the client will use for `GET /stream/logs`.

        Useful for debugging auth problems (clock skew, token parsing, etc.).
        '''
        return self._build_auth_headers('GET', '/stream/logs', None)

    def _extract(self, data, field):
        if not isinstance(data, dict):
            raise HungerBridgeError('_extract() expects a dict response')
        return data.get(field)

    # raw endpoints
    def ping(self) -> dict:
        return self._get('ping')

    def info(self) -> dict:
        return self._get('info')

    def status(self) -> dict:
        return self._get('status')

    def tps(self) -> dict:
        return self._get('tps')

    def players(self) -> dict:
        return self._get('players')

    # public api
    def runCommand(
        self,
        command: str,
        show_console: bool = False,
        silent: bool = False,
        normalize: bool = True
    ):
        '''
        Execute a command on the server.
        Returns normalized output unless normalize=False.
        '''
        data = self._post('run', {
            'command': command,
            'silent': silent,
            'show_console': show_console
        })
        if not normalize:
            return data
        if isinstance(data, dict):
            out = data.get('output')
            if isinstance(out, list):
                return '\n'.join(str(x) for x in out)
            if isinstance(out, (str, bytes)):
                return out
            return None
        if isinstance(data, list):
            return '\n'.join(str(x) for x in data)
        if isinstance(data, (str, bytes)):
            return data
        return None

    def log(self, message: str, level: str = 'info') -> dict:
        '''Logs a message to the server console'''
        valid_levels = ['info', 'warn', 'error', None]
        if level not in valid_levels:
            raise InvalidLevelError(f'\'{level}\' is not a valid log level')
        if level is not None:
            return self._post('log', {
                'level': level,
                'message': message
            })
        no_level_message = ('\b' * 20) + message
        return self._post('log', {
            'level': 'info',
            'message': no_level_message
        })

    # convenience getters
    def getPing(self) -> int:
        '''Round-trip latency (ms) measured client-side.'''
        start = time.time()
        self.ping()
        end = time.time()
        return int((end - start) * 1000)

    def getVersion(self) -> str | None:
        '''Returns HungerBridge version'''
        info = self.info()
        bridge = self._extract(info, 'bridge')
        return bridge.get('version') if isinstance(bridge, dict) else None

    def getPlatform(self) -> str | None:
        '''Returns server platform'''
        info = self.info()
        bridge = self._extract(info, 'bridge')
        return bridge.get('platform') if isinstance(bridge, dict) else None

    def getMinecraftVersion(self) -> str | None:
        '''Returns Minecraft version'''
        info = self.info()
        bridge = self._extract(info, 'bridge')
        return bridge.get('minecraft') if isinstance(bridge, dict) else None

    def getStatus(self) -> bool:
        '''Validates connection status'''
        return self._extract(self.status(), 'ok')

    def getTPS(self, mode: str = 'current') -> float:
        '''
        Returns TPS values:
        - current:   EMA20
        - 1m:        EMA1200
        - 5m:        EMA6000
        - tick_time: avg tick time (ms)
        '''
        data = self.tps()
        if mode == 'current':
            return self._extract(data, 'tps')
        if mode == '1m':
            return self._extract(data, 'tps_1m')
        if mode == '5m':
            return self._extract(data, 'tps_5m')
        if mode == 'tick_time':
            return self._extract(data, 'tick_time_ms')

        raise InvalidModeError(f'Invalid mode: \'{mode}\'')

    def getPlayers(self, mode: str = 'count') -> int | list:
        '''
        Returns:
        - count: number of players
        - list: list of player names
        '''
        data = self.players()

        if mode == 'count':
            return self._extract(data, 'count')
        if mode == 'list':
            return self._extract(data, 'players')
        raise InvalidModeError(f'Invalid mode: \'{mode}\'')

    # --- admin endpoints ---
    def list_tokens(self) -> dict:
        '''List tokens (admin). Returns mapping of token metadata.'''
        return self._get('admin/tokens/list')

    def create_token(
        self,
        token_id: str | None = None,
        name: str | None = None,
        expiry: int | None = None,
        whitelist: list | None = None,
        blacklist: list | None = None,
    ) -> dict:
        '''Create a token using the explicit `id`, optional `name`, and optional `expiry`.'''
        if token_id is None or not str(token_id).strip():
            raise HungerBridgeError('token_id is required')

        payload = {'id': str(token_id)}
        if name is not None and str(name).strip():
            payload['name'] = str(name)
        if expiry is not None:
            payload['expiry'] = int(expiry)
        if whitelist is not None:
            payload['whitelist'] = whitelist
        if blacklist is not None:
            payload['blacklist'] = blacklist
        return self._post('admin/tokens/create', payload)

    def revoke_token(self, token_id: str) -> dict:
        '''Revoke a token by id.'''
        return self._post('admin/tokens/revoke', {'id': token_id})

    def rotate_token(self, token_id: str) -> dict:
        '''Rotate a token secret; returns new id/secret pair.'''
        return self._post('admin/tokens/rotate', {'id': token_id})

    def admin_status(self) -> dict:
        '''Get admin/status info (rate limits, ACLs).'''
        return self._get('admin/status')


    def ip_status(self) -> dict:
        '''Get configured IP whitelist/blacklist.'''
        return self._get('admin/ip')

    def get_audit(self, n: int = 20) -> list:
        '''Get last N audit log lines.'''
        # audit endpoint expects ?n=<int>
        return self._get(f'admin/audit?n={int(n)}')

    def reload_config(self) -> dict:
        '''Trigger config reload on server.'''
        return self._post('admin/reload', {})
