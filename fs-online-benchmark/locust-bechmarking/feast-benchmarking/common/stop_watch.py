import inspect
import time
from locust import events


def stopwatch(func):
    """Decorator to measure and report function execution time to Locust."""
    def wrapper(*args, **kwargs):
        previous_frame = inspect.currentframe().f_back
        _, _, task_name, _, _ = inspect.getframeinfo(previous_frame)

        start = time.time()
        result = None
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            total = int((time.time() - start) * 1000)
            events.request.fire(
                request_type=task_name[:3].upper(),
                name=task_name,
                response_time=total,
                exception=e,
                response_length=0
            )
        else:
            total = int((time.time() - start) * 1000)
            events.request.fire(
                request_type=task_name[:3].upper(),
                name=task_name,
                response_time=total,
                response_length=0,
            )
        return result

    return wrapper
