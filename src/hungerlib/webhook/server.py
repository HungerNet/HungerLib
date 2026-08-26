import uvicorn
from fastapi import FastAPI, Request, Header, HTTPException

class WebhookServer:
    def __init__(self, port: int, token: str, host: str = "0.0.0.0", logLevel: str = "info"):
        self.port = port
        self.token = token
        self.host = host
        self.logLevel = logLevel

        self.app = FastAPI()
        self._server = None

        # routing tables
        self._endpointHandlers: dict[str, callable] = {}
        self._eventHandlers: dict[str, callable] = {}

    def addEndpoint(self, path: str, handler: callable):
        # register endpoint
        self._endpointHandlers[path] = handler

        @self.app.post(path)
        async def _endpoint(request: Request, x_webhook_token: str | None = Header(None)):
            if x_webhook_token != self.token:
                raise HTTPException(status_code=401, detail="invalid token")

            data = await request.json()
            event = (data.get("event") or "").lower()

            # endpoint handler
            await handler(event, data)

            # event handler
            if event in self._eventHandlers:
                await self._eventHandlers[event](data)

            return {"status": "ok"}

    def addHandler(self, event: str, handler: callable):
        # register event handler
        self._eventHandlers[event.lower()] = handler

    async def start(self):
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level=self.logLevel
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self):
        # stop server
        if self._server:
            self._server.should_exit = True
