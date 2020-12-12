import time


async def with_ratelimit(client, method, *args, **kwargs):
    func = getattr(client, method)
    response = await func(*args, **kwargs)
    if getattr(response, "status_code", None) == "M_LIMIT_EXCEEDED":
        time.sleep(3)
        return with_ratelimit(client, method, *args, **kwargs)
    return response
