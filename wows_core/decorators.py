import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

def async_run_in_executor(executor=None):
    """
    装饰器：将异步函数放入指定的 Executor（线程池或进程池）中运行。
    默认使用 ThreadPoolExecutor。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_running_loop()
            # 如果没有传递 executor，则使用默认的线程池
            exec_ = executor or ThreadPoolExecutor()

            # 异步函数通过 run() 执行
            result = await loop.run_in_executor(exec_, _run_async_function, func, *args, **kwargs)
            return result

        return wrapper
    return decorator

def _run_async_function(func, *args, **kwargs):
    """
    将异步函数在同步上下文中执行的包装器
    """
    return asyncio.run(func(*args, **kwargs))

def sync_run_in_executor(executor=None):
    """
    装饰器：将步步函数放入指定的 Executor（线程池或进程池）中运行。
    默认使用 ThreadPoolExecutor。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_running_loop()
            # 如果没有传递 executor，则使用默认的线程池
            exec_ = executor or ThreadPoolExecutor()

            # 异步函数通过 run() 执行
            result = await loop.run_in_executor(exec_, func, *args, **kwargs)
            return result

        return wrapper
    return decorator