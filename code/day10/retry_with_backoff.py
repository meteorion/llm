import time
import random
import functools

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                        retryable_exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function with exponential backoff.

    :param max_retries: Maximum number of retries before giving up.
    :param base_delay: Base delay between retries.
    :param retryable_exceptions: Tuple of exceptions that should trigger a retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        break
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"第 {attempt + 1} 次失败：{e}，{delay:.1f}s 后重试...")
                    time.sleep(delay)
            raise RuntimeError(f"重试 {max_retries} 次后仍失败：{last_error}")
        return wrapper
    return decorator