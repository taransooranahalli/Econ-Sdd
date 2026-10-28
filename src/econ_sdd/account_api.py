"""Account and saved-plan routes; all private access is owner scoped."""
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import HTMLResponse,JSONResponse
from starlette.concurrency import run_in_threadpool

from .accounts import ABSOLUTE_SECONDS,AccountError,AccountStore
from .finance.cash_flow import CASH_FLOW_MODEL_VERSION,CashFlowBudget,calculate_cash_flow,plain_text
from .finance.goals import GOAL_MODEL_VERSION,SavingsGoal,solve_goal
from .finance.savings import MODEL_VERSION,SavingsScenario,calculate_savings
from .serialization.cash_flow import cash_flow_record,cash_flow_display
from .serialization.records import result_record,result_display

VERSIONS={'savings':MODEL_VERSION,'goal':GOAL_MODEL_VERSION,'cash_flow':CASH_FLOW_MODEL_VERSION}


def fields(data,required):
    if not isinstance(data,dict) or set(data)!=set(required):raise AccountError(422,'Use the required fields for this request.')


def normalize_plan(data,*,updating=False):
    fields(data,{'title','kind','inputs','revision'} if updating else {'title','kind','inputs'})
    if not plain_text(data['title'],required=True):raise AccountError(422,'Enter a plan name of 1–80 plain-text characters.','title')
    kind=data['kind']
    if not isinstance(kind,str) or kind not in VERSIONS:raise AccountError(422,'Choose a supported calculator.')
    if updating and (type(data['revision']) is not int or data['revision']<1):raise AccountError(422,'Use the current saved-plan revision.')
    model={'savings':SavingsScenario,'goal':SavingsGoal,'cash_flow':CashFlowBudget}[kind].from_mapping(data['inputs'])
    # Validate arithmetic before persisting original inputs; no derived result is trusted or stored.
    calculate_model(kind,model)
    return {'title':data['title'].strip(),'kind':kind,'model_version':VERSIONS[kind],'inputs':model.as_record()}


def calculate_model(kind,model):
    if kind=='cash_flow':
        result=calculate_cash_flow(model);return {**cash_flow_record(result),'display':cash_flow_display(result)}
    result=solve_goal(model) if kind=='goal' else calculate_savings(model)
    return {**result_record(result),'display':result_display(result)}


def reopened_calculation(value):
    kind=value['kind']
    if kind not in VERSIONS or value['model_version']!=VERSIONS[kind]:raise AccountError(422,'This saved model needs a reviewed migration before it can be opened.')
    model={'savings':SavingsScenario,'goal':SavingsGoal,'cash_flow':CashFlowBudget}[kind].from_mapping(value['inputs'])
    return calculate_model(kind,model)


def install_account_routes(app,store: AccountStore|None,csrf_token: str,payload,static: Path,*,secure=False):
    cookie_name='__Host-econ_session' if secure else 'econ_dev_session'

    async def session_for(request,*,mutation=False):
        if store is None:raise AccountError(503,'Accounts are unavailable. Initialize account storage before starting the app.')
        session=await run_in_threadpool(store.session,request.cookies.get(cookie_name))
        if session is None:raise AccountError(401,'Sign in to access your saved plans.')
        if mutation:
            token=request.headers.get('x-account-csrf','')
            if not secrets.compare_digest(token.encode(),session.csrf.encode()):raise AccountError(403,'Refresh your account session before making changes.')
        return session

    async def signed_response(token,*,recovery=None):
        session=await run_in_threadpool(store.session,token)
        data={'available':True,'authenticated':True,'user':{'id':session.user_id,'username':session.username},'csrf_token':session.csrf}
        if recovery:data['recovery_code']=recovery
        response=JSONResponse(data)
        response.set_cookie(cookie_name,token,max_age=ABSOLUTE_SECONDS,httponly=True,secure=secure,samesite='strict',path='/')
        return response

    def available():
        if store is None:raise AccountError(503,'Accounts are unavailable. Initialize account storage before starting the app.')

    def client_key(request):return request.client.host if request.client else 'unknown'

    @app.get('/account',response_class=HTMLResponse)
    @app.get('/plans',response_class=HTMLResponse)
    def account_page(request: Request):
        return HTMLResponse((static/('plans.html' if request.url.path=='/plans' else 'account.html')).read_text().replace('__CSRF_TOKEN__',csrf_token))

    @app.get('/api/account/session')
    async def account_session(request: Request):
        session=await run_in_threadpool(store.session,request.cookies.get(cookie_name)) if store else None
        return {'available':store is not None,'authenticated':session is not None,
                **({'user':{'id':session.user_id,'username':session.username},'csrf_token':session.csrf} if session else {})}

    @app.post('/api/account/register')
    async def register(request: Request):
        available();data,error=await payload(request)
        if error is not None:return error
        fields(data,{'username','password'})
        token,recovery=await run_in_threadpool(store.register,data['username'],data['password'],client_key(request),request.cookies.get(cookie_name))
        return await signed_response(token,recovery=recovery)

    @app.post('/api/account/login')
    async def login(request: Request):
        available();data,error=await payload(request)
        if error is not None:return error
        fields(data,{'username','password'})
        token=await run_in_threadpool(store.login,data['username'],data['password'],client_key(request),request.cookies.get(cookie_name))
        return await signed_response(token)

    @app.post('/api/account/recover')
    async def recover(request: Request):
        available();data,error=await payload(request)
        if error is not None:return error
        fields(data,{'username','recovery_code','password'})
        token,recovery=await run_in_threadpool(store.recover,data['username'],data['recovery_code'],data['password'],client_key(request))
        return await signed_response(token,recovery=recovery)

    @app.post('/api/account/password')
    async def password(request: Request):
        session=await session_for(request,mutation=True);data,error=await payload(request)
        if error is not None:return error
        fields(data,{'current_password','password'})
        token,recovery=await run_in_threadpool(store.replace_password,session,data['current_password'],data['password'])
        return await signed_response(token,recovery=recovery)

    @app.post('/api/account/logout')
    async def logout(request: Request):
        session=await session_for(request,mutation=True);data,error=await payload(request)
        if error is not None:return error
        fields(data,set());await run_in_threadpool(store.logout,session)
        response=JSONResponse({'authenticated':False,'available':True})
        response.delete_cookie(cookie_name,path='/',secure=secure,httponly=True,samesite='strict')
        return response

    @app.get('/api/plans')
    async def plans(request: Request):
        session=await session_for(request)
        return {'plans':await run_in_threadpool(store.list_plans,session)}

    @app.get('/api/plans/{plan_id}')
    async def open_plan(plan_id: str,request: Request):
        session=await session_for(request);value=await run_in_threadpool(store.open_plan,session,plan_id)
        record=await run_in_threadpool(reopened_calculation,value)
        return {'plan':{key:value[key] for key in ('id','title','kind','revision','updated')},'calculation':record}

    @app.post('/api/plans')
    async def save_plan(request: Request):
        session=await session_for(request,mutation=True);data,error=await payload(request)
        if error is not None:return error
        value=await run_in_threadpool(normalize_plan,data)
        result=await run_in_threadpool(store.save_plan,session,value)
        return {'plan':{**result,'title':value['title'],'kind':value['kind']}}

    @app.post('/api/plans/{plan_id}/replace')
    async def replace_plan(plan_id: str,request: Request):
        session=await session_for(request,mutation=True);data,error=await payload(request)
        if error is not None:return error
        value=await run_in_threadpool(normalize_plan,data,updating=True)
        result=await run_in_threadpool(store.save_plan,session,value,plan_id=plan_id,revision=data['revision'])
        return {'plan':{**result,'title':value['title'],'kind':value['kind']}}

    @app.post('/api/plans/{plan_id}/delete')
    async def delete_plan(plan_id: str,request: Request):
        session=await session_for(request,mutation=True);data,error=await payload(request)
        if error is not None:return error
        fields(data,{'revision'});await run_in_threadpool(store.delete_plan,session,plan_id,data['revision'])
        return {'deleted':True}
