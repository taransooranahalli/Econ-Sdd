"""Market reads share account/session and CSRF boundaries; demo never calls a provider."""
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .accounts import AccountError
from .market.models import MarketError, demo


def install_market_routes(app, service, session_for, payload, static, csrf_token):
    @app.exception_handler(MarketError)
    async def market_error(_request, error):
        return JSONResponse({'errors':{'form':error.message},'code':error.code},status_code=error.status,
                            headers={'Retry-After':str(error.retry_after)} if error.retry_after else None)

    @app.get('/stocks', response_class=HTMLResponse)
    def stocks_page():
        return HTMLResponse((static/'stocks.html').read_text().replace('__CSRF_TOKEN__',csrf_token))

    @app.get('/api/market/status')
    async def market_status(request: Request):
        try:
            session = await session_for(request)
        except AccountError as error:
            if error.status not in (401,503):
                raise
            return {'authenticated':False,'configured':False,'accounts_available':error.status != 503}
        return {'authenticated':True, **service.status(session.user_id)}

    async def body_for(request, required):
        data, error = await payload(request)
        if error is not None:
            return None, error
        if not isinstance(data, dict) or set(data) != set(required):
            raise MarketError('fields','Use the required fields for this market request.',422)
        return data, None

    @app.post('/api/market/example')
    async def example(request: Request):
        _, error = await body_for(request, set())
        return error if error is not None else demo()

    @app.post('/api/market/search')
    async def search(request: Request):
        session = await session_for(request, mutation=True)
        data, error = await body_for(request, {'query'})
        if error is not None:
            return error
        return await run_in_threadpool(service.search, session.user_id, data['query'])

    @app.post('/api/market/prices')
    async def prices(request: Request):
        session = await session_for(request, mutation=True)
        data, error = await body_for(request, {'instrument_id','mode','days'})
        if error is not None:
            return error
        return await run_in_threadpool(service.detail, session.user_id, data['instrument_id'], data['mode'], data['days'])
