import asyncio
from unittest.mock import patch

from app.cloud_web import OperationalErrors


def test_cloud_wrapper_preserves_errors_and_only_reports_category():
    async def broken(scope, receive, send):
        raise RuntimeError('private assignment and credentials')

    with patch('app.cloud_web.report') as report:
        try:
            asyncio.run(OperationalErrors(broken)({'type': 'http'}, None, None))
        except RuntimeError:
            pass
        else:
            raise AssertionError('Must not swallow application failure')
        report.assert_called_once_with('core_unhandled')


def test_cloud_wrapper_passes_success_without_reporting():
    async def healthy(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 204})

    from unittest.mock import AsyncMock
    send = AsyncMock()
    with patch('app.cloud_web.report') as report:
        asyncio.run(OperationalErrors(healthy)({'type': 'http'}, None, send))
        report.assert_not_called()
    assert send.call_args.args[0]['status'] == 204
