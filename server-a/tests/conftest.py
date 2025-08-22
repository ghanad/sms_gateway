import sys, os, asyncio, inspect
import pytest
import httpx

# Patch httpx.AsyncClient to accept the deprecated 'app' argument for compatibility
_OriginalAsyncClient = httpx.AsyncClient

class _PatchedAsyncClient(httpx.AsyncClient):
    def __init__(self, *args, app=None, **kwargs):
        if app is not None:
            kwargs.setdefault("transport", httpx.ASGITransport(app=app))
            kwargs.setdefault("base_url", "http://testserver")
        super().__init__(*args, **kwargs)

httpx.AsyncClient = _PatchedAsyncClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if asyncio.iscoroutinefunction(pyfuncitem.obj):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sig = inspect.signature(pyfuncitem.obj)
            kwargs = {name: pyfuncitem.funcargs[name] for name in sig.parameters}
            for name, value in pyfuncitem.funcargs.items():
                if name not in kwargs:
                    pyfuncitem.obj.__globals__[name] = value
                    if name == "mock_settings":
                        import app.idempotency as _idem
                        _idem.settings = value
            loop.run_until_complete(pyfuncitem.obj(**kwargs))
        finally:
            loop.close()
        return True
