"""Portfolio definitions and owner/session-bound valuation; no client-supplied prices."""
from fastapi import Request
from fastapi.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool

from .finance.portfolios import PortfolioDefinition
from .market.models import MarketError
from .serialization.portfolios import definition_record, definition_from_record, export_definition


def install_portfolio_routes(app, service, session_for, payload, static, csrf_token):
    @app.get('/portfolios',response_class=HTMLResponse)
    def page():
        return HTMLResponse((static/'portfolios.html').read_text().replace('__CSRF_TOKEN__',csrf_token))

    async def body_for(request, required):
        data,error=await payload(request)
        if error is not None:return None,error
        if not isinstance(data,dict) or set(data)!=required:
            raise MarketError('fields','Use the required portfolio request fields only.',422)
        return data,None

    @app.post('/api/portfolios/validate')
    async def validate(request: Request):
        data,error=await body_for(request,{'definition'})
        if error is not None:return error
        return definition_record(PortfolioDefinition.from_mapping(data['definition']))

    @app.post('/api/portfolios/import')
    async def import_definition(request: Request):
        data,error=await payload(request)
        if error is not None:return error
        return definition_record(definition_from_record(data))

    @app.post('/api/portfolios/export')
    async def export(request: Request):
        data,error=await body_for(request,{'definition'})
        if error is not None:return error
        definition=PortfolioDefinition.from_mapping(data['definition'])
        return Response(export_definition(definition),media_type='application/json',
                        headers={'Content-Disposition':'attachment; filename="finance-portfolio-definition-USD.json"'})

    @app.post('/api/portfolios/example')
    async def example(request: Request):
        data,error=await payload(request)
        if error is not None:return error
        if not isinstance(data,dict) or set(data) not in (set(),{'definition'}):
            raise MarketError('fields','Use the example request fields only.',422)
        definition=PortfolioDefinition.from_mapping(data['definition']) if data else None
        return await run_in_threadpool(service.example,definition)

    @app.post('/api/portfolios/capture')
    async def capture(request: Request):
        session=await session_for(request,mutation=True)
        data,error=await body_for(request,{'definition','input_revision'})
        if error is not None:return error
        definition=PortfolioDefinition.from_mapping(data['definition'])
        return await run_in_threadpool(service.capture,session,definition,data['input_revision'])

    @app.post('/api/portfolios/value')
    async def value(request: Request):
        session=await session_for(request,mutation=True)
        data,error=await body_for(request,{'definition','input_revision','capture_id'})
        if error is not None:return error
        definition=PortfolioDefinition.from_mapping(data['definition'])
        return await run_in_threadpool(service.value,session,definition,data['capture_id'],data['input_revision'])
