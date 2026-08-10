import requests

class WebhookClient:
    def __init__(self, url: str, token: str, timeout: int = 5):
        self.url = url
        self.token = token
        self.timeout = timeout

    def send(self, event: str, **ctx):
        payload = {'event': event, **ctx}

        resp = requests.post(
            self.url,
            json=payload,
            headers={'x-webhook-token': self.token},
            timeout=self.timeout
        )

        resp.raise_for_status()
        return resp.json()
