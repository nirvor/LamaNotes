from starlette.responses import JSONResponse


class PrivateRequestLimit:
    """Bound private request bodies before multipart parsing/spooling."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        intake = "/api/share-intake/v1/" in path
        if scope["type"] != "http" or ("/api/private/v1/" not in path and not intake):
            return await self.app(scope, receive, send)
        limit = 1024 if intake else (21 if path.endswith("/assets") else 8) * 1024 * 1024
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                response = JSONResponse(
                    {"detail": "Private request is too large."},
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        async def no_store(message):
            if message["type"] == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message["headers"]
                    if k.lower() not in {b"cache-control", b"vary"}
                ]
                message["headers"] = headers + [
                    (b"cache-control", b"no-store"),
                    (b"vary", b"Authorization, Cookie"),
                ]
            await send(message)

        await self.app(scope, replay, no_store)
