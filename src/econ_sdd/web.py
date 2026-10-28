"""Loopback web adapter. Financial logic remains independent of the web stack."""

from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .accounts import AccountStore,AccountError,default_paths
from .security import Keyring,VaultError
from .account_api import install_account_routes
from .finance.currencies import CURRENCIES, DEFAULT_CURRENCY
from .finance.cash_flow import CASH_FLOW_MODEL_VERSION, CashFlowBudget, calculate_cash_flow
from .finance.goals import GOAL_MODEL_VERSION, SavingsGoal, solve_goal
from .finance.savings import MODEL_VERSION, MAX_MONTHS, CalculationUnavailable, ScenarioError, SavingsScenario, calculate_savings
from .serialization.records import (MAX_FILE_BYTES, calculation_from_record, calculation_input,
    display_record, export_csv, export_json, load_json, projection_record, result_record, result_display)
from .serialization.cash_flow import (budget_from_record, cash_flow_record, cash_flow_display,
                                      export_cash_flow_json, export_cash_flow_csv)

from .finance.investments import MODEL_VERSION as INVESTMENT_MODEL_VERSION, InvestmentScenario, calculate_investments
from .serialization.investments import (scenario_from_record, investment_record, investment_display,
                                        export_investment_json, export_investment_csv)

STATIC = Path(__file__).parent / "static"


def create_app(*,account_store: AccountStore|None=None,public_origin: str|None=None) -> FastAPI:
    if public_origin:
        origin_parts=urlsplit(public_origin)
        if (origin_parts.scheme!='https' or not origin_parts.hostname or origin_parts.username or origin_parts.password
                or origin_parts.path or origin_parts.query or origin_parts.fragment or '*' in public_origin):
            raise ValueError('A public origin must be an exact HTTPS origin with no path.')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, debug=False)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[origin_parts.hostname] if public_origin else ["127.0.0.1", "localhost"], www_redirect=False)
    csrf_token = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if public_origin and request.url.scheme!='https':
            response=JSONResponse({'errors':{'form':'HTTPS is required for accounts on this origin.'}},status_code=426)
        else:
            response=None
        if response is None and request.method in ("POST","PUT","PATCH","DELETE"):
            origin = request.headers.get("origin")
            expected_origin = public_origin or f"{request.url.scheme}://{request.headers.get('host', '')}"
            if (origin is not None and origin != expected_origin) or request.headers.get("sec-fetch-site") == "cross-site":
                response=JSONResponse({"errors": {"form": "Use this calculator from its own page."}}, status_code=403)
            token = request.headers.get("x-csrf-token", "")
            if response is None and not secrets.compare_digest(token.encode("utf-8"), csrf_token.encode("ascii")):
                response=JSONResponse({"errors": {"form": "Refresh the page and try again."}}, status_code=403)
            if response is None and request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                response=JSONResponse({"errors": {"form": "Use a JSON request."}}, status_code=415)
        if response is None:response = await call_next(request)
        if public_origin:response.headers["Strict-Transport-Security"]="max-age=31536000"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.exception_handler(AccountError)
    async def account_error(_request: Request,exc: AccountError):
        return JSONResponse({'errors':exc.errors},status_code=exc.status,headers={'Retry-After':'900'} if exc.status==429 else None)

    @app.exception_handler(VaultError)
    @app.exception_handler(sqlite3.Error)
    async def storage_error(_request: Request,_exc: Exception):
        return JSONResponse({'errors':{'form':'Account storage is unavailable. Check the database and original keyring.'}},status_code=503)

    @app.exception_handler(ScenarioError)
    async def scenario_error(_request: Request, exc: ScenarioError):
        return JSONResponse({"errors": exc.errors}, status_code=422)

    @app.exception_handler(CalculationUnavailable)
    async def unavailable(_request: Request, _exc: CalculationUnavailable):
        return JSONResponse({"errors": {"form": "The projection is unavailable for these assumptions."}}, status_code=422)

    async def payload(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_FILE_BYTES:
                return None, JSONResponse({"errors": {"file": "Use a JSON file no larger than 1 MiB."}}, status_code=413)
        return load_json(bytes(body)), None

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse((STATIC / "index.html").read_text().replace("__CSRF_TOKEN__", csrf_token))

    @app.get("/cash-flow", response_class=HTMLResponse)
    def cash_flow_page():
        return HTMLResponse((STATIC / "cash-flow.html").read_text().replace("__CSRF_TOKEN__", csrf_token))

    @app.get("/investments", response_class=HTMLResponse)
    def investments_page():
        return HTMLResponse((STATIC / "investments.html").read_text().replace("__CSRF_TOKEN__", csrf_token))

    @app.get("/api/config")
    def config():
        return {"default_currency": DEFAULT_CURRENCY, "app_version": __version__, "model_version": MODEL_VERSION,
                "investment_model_version": INVESTMENT_MODEL_VERSION, "goal_model_version": GOAL_MODEL_VERSION, "cash_flow_model_version": CASH_FLOW_MODEL_VERSION,
                "max_months": MAX_MONTHS, "max_upload_bytes": MAX_FILE_BYTES,
                "currencies": [{"code": c.code, "name": c.name, "symbol": c.symbol, "minor_digits": c.minor_digits}
                               for c in CURRENCIES.values()]}

    @app.post("/api/calculate")
    async def calculate(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        projection = calculate_savings(SavingsScenario.from_mapping(data))
        return {**projection_record(projection), "display": display_record(projection)}

    @app.post("/api/goal")
    async def goal(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        result = solve_goal(SavingsGoal.from_mapping(data))
        return {**result_record(result), "display": result_display(result)}

    @app.post("/api/import")
    async def import_scenario(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        inputs = calculation_from_record(data)
        result = solve_goal(inputs) if isinstance(inputs, SavingsGoal) else calculate_savings(inputs)
        return {**result_record(result), "display": result_display(result)}

    @app.post("/api/cash-flow")
    async def cash_flow(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_cash_flow(CashFlowBudget.from_mapping(data))
        return {**cash_flow_record(result), "display": cash_flow_display(result)}

    @app.post("/api/cash-flow/import")
    async def cash_flow_import(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_cash_flow(budget_from_record(data))
        return {**cash_flow_record(result), "display": cash_flow_display(result)}

    @app.post("/api/cash-flow/export/{kind}")
    async def cash_flow_export(request: Request, kind: str):
        if kind not in ("json", "csv"):
            return JSONResponse({"errors": {"file": "Choose JSON or CSV export."}}, status_code=404)
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_cash_flow(CashFlowBudget.from_mapping(data))
        body = export_cash_flow_json(result) if kind == "json" else export_cash_flow_csv(result)
        return Response(body, media_type="application/json" if kind == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="econ-cash-flow-{result.budget.currency}.{kind}"'})

    @app.post("/api/investments")
    async def investments(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_investments(InvestmentScenario.from_mapping(data))
        return {**investment_record(result), "display": investment_display(result)}

    @app.post("/api/investments/import")
    async def investments_import(request: Request):
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_investments(scenario_from_record(data))
        return {**investment_record(result), "display": investment_display(result)}

    @app.post("/api/investments/export/{kind}")
    async def investments_export(request: Request, kind: str):
        if kind not in ("json", "csv"):
            return JSONResponse({"errors": {"file": "Choose JSON or CSV export."}}, status_code=404)
        data, error = await payload(request)
        if error is not None:
            return error
        result = calculate_investments(InvestmentScenario.from_mapping(data))
        body = export_investment_json(result) if kind == "json" else export_investment_csv(result)
        return Response(body, media_type="application/json" if kind == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="econ-investments-{result.scenario.currency}.{kind}"'})

    @app.post("/api/export/{kind}")
    async def export(request: Request, kind: str):
        if kind not in ("json", "csv"):
            return JSONResponse({"errors": {"file": "Choose JSON or CSV export."}}, status_code=404)
        data, error = await payload(request)
        if error is not None:
            return error
        inputs = calculation_input(data)
        projection = solve_goal(inputs) if isinstance(inputs, SavingsGoal) else calculate_savings(inputs)
        body = export_json(projection) if kind == "json" else export_csv(projection)
        return Response(body, media_type="application/json" if kind == "json" else "text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{"econ-goal" if isinstance(inputs, SavingsGoal) else "econ-savings"}-{inputs.currency}.{kind}"'})

    install_account_routes(app,account_store,csrf_token,payload,STATIC,secure=bool(public_origin))
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def create_local_app() -> FastAPI:
    import os
    database,key_file=default_paths()
    if not database.exists():raise VaultError('Initialize accounts first: python -m econ_sdd.accounts init')
    return create_app(account_store=AccountStore(database,Keyring.load(key_file)),public_origin=os.environ.get('ECON_PUBLIC_ORIGIN'))
