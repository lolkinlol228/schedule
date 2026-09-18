import copy
import hashlib
import logging
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError, model_validator, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware
from urllib.parse import urlparse
from sqlalchemy import select, delete
from .domain import Strict, MODELS, Settings, validate_data, slot_stride, bell_label
from .storage import make_engine, users, sessions, versions, jobs, audit, demo_backup, now, uid, log, get_data, save_data
from .scheduling import prepare_errors, events, indexes, validate_schedule, score, DAYS, capacity_issues, diagnose
from .solver import solve
from .demo import demo_data
from .exports import export
from .recommendations import proposals, coverage
from .validation import validation_errors
from .scenarios import scenario_data, catalogue

class Password(Strict):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=False)
    password: str = Field(min_length=12,max_length=128)
class Login(Strict):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=False)
    password: str = Field(min_length=1,max_length=128)
class ChangePassword(Password):
    current: str = Field(min_length=1,max_length=128)
class DataWrite(Strict):
    revision: int = Field(ge=0)
    record: dict
class SettingsWrite(Strict):
    revision: int = Field(ge=0)
    settings: Settings
class DemoSwitch(Strict):
    revision: int = Field(ge=0)
    scenario: str = ''
    seed: int = Field(42,ge=0,le=2147483647)
class Generate(Strict):
    week: str = ''
    seed: int = Field(42,ge=0,le=2147483647)
    seconds: int = Field(10,ge=1,le=10)
    source_id: str = ''
    repair_scope: Literal['teachers','rooms'] = 'teachers'
    repair_resource: str = ''
    repair_days: list[int] = Field(default_factory=lambda:list(range(5)))
    expand_percent: int = Field(5,ge=0,le=100)
    @model_validator(mode='after')
    def valid_week(self):
        if self.week:
            try:
                if date.fromisoformat(self.week).weekday()!=0: raise ValueError()
            except ValueError: raise ValueError('Выберите понедельник нужной недели')
        if any(d not in range(5) for d in self.repair_days): raise ValueError('Некорректные дни ремонта')
        return self
class Assignment(Strict):
    teacher_id: str
    room_id: str
class Lesson(Strict):
    id: str
    slot: int = Field(ge=0,le=79)
    parts: list[Assignment] = Field(min_length=1,max_length=10)
    lock: Literal['free','preferred','locked'] = 'free'
    origin: Literal['generator','manual','replacement','merge'] = 'manual'
class Edit(Strict):
    lessons: list[Lesson] = Field(max_length=2000)
class StatusChange(Strict):
    status: Literal['draft','review','approved','published','archived']

def create_app(database_url=None):
    app=FastAPI(title='Ритм — API расписания',docs_url=None,redoc_url=None,openapi_url=None)
    allowed_hosts=['127.0.0.1','localhost','testserver']
    configured_host=urlparse(os.getenv('APP_ORIGIN','')).hostname
    if configured_host:allowed_hosts.append(configured_host)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=allowed_hosts)
    engine=make_engine(database_url); app.state.engine=engine
    hasher=PasswordHasher(); dummy=hasher.hash(secrets.token_urlsafe(32)); failures=[]; guard=threading.Lock()
    pool=ThreadPoolExecutor(max_workers=1); controls={}
    with engine.begin() as c:
        for j in c.execute(select(jobs)).mappings():
            if j['payload'].get('status')=='running': c.execute(jobs.update().where(jobs.c.id==j['id']).values(payload={**j['payload'],'status':'interrupted','errors':['Сервер перезапущен. Запустите генерацию повторно.']}))

    @app.middleware('http')
    async def security(request, call_next):
        origin=request.headers.get('origin'); expected=os.getenv('APP_ORIGIN')
        allowed={expected} if expected else {str(request.base_url).rstrip('/'),'http://localhost:5173','http://127.0.0.1:5173'}
        if request.method not in ('GET','HEAD','OPTIONS') and (origin and origin not in allowed or request.headers.get('sec-fetch-site')=='cross-site'):
            return JSONResponse({'detail':'Запрос с другого сайта запрещён'},403)
        try: length=int(request.headers.get('content-length','0'))
        except ValueError: return JSONResponse({'detail':'Некорректный запрос'},400)
        if length>2_000_000: return JSONResponse({'detail':'Запрос слишком большой'},413)
        try: response=await call_next(request)
        except Exception:
            correlation=uid(); logging.exception('Unhandled request %s',correlation)
            response=JSONResponse({'detail':f'Операция не выполнена. Код обращения: {correlation}'},500)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
        if request.url.path.startswith('/api'): response.headers['Cache-Control']='no-store'
        if getattr(request.state,'refresh_session',None):
            response.set_cookie('session',request.state.refresh_session,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=1800)
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse({'detail':'Проверьте заполнение полей','errors':validation_errors(exc.errors())},422)

    def auth(request:Request, allow_change=False):
        token=request.cookies.get('session',''); hashed=hashlib.sha256(token.encode()).hexdigest()
        with engine.begin() as c:
            row=c.execute(select(sessions).where(sessions.c.id==hashed)).mappings().first()
            if not row or (datetime.now(timezone.utc)-datetime.fromisoformat(row['seen'])).total_seconds()>1800: raise HTTPException(401,'Войдите в систему')
            if request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']): raise HTTPException(403,'Проверка безопасности не пройдена. Обновите страницу')
            user=c.execute(select(users)).mappings().one()
            if user['must_change'] and not allow_change: raise HTTPException(403,'Смените первоначальный пароль')
            c.execute(sessions.update().where(sessions.c.id==hashed).values(seen=now()))
            request.state.refresh_session=token
            return dict(row)|{'must_change':bool(user['must_change'])}
    def authorized(request:Request): return auth(request)

    @app.get('/api/auth/status')
    def auth_status():
        with engine.connect() as c: return {'setup_required':c.execute(select(users)).first() is None}

    @app.post('/api/auth/setup',status_code=201)
    def setup(body:Password):
        with guard,engine.begin() as c:
            if c.execute(select(users)).first(): raise HTTPException(409,'Администратор уже создан')
            c.execute(users.insert().values(id=1,password=hasher.hash(body.password),must_change=1)); log(c,'Создание администратора')
        return {'ok':True}

    @app.post('/api/auth/login')
    def login(body:Login,response:Response,request:Request):
        with guard:
            cutoff=time.monotonic()-300; failures[:]=[t for t in failures if t>cutoff]
            if len(failures)>=5: raise HTTPException(429,'Слишком много попыток. Повторите через 5 минут')
            with engine.begin() as c:
                user=c.execute(select(users)).mappings().first()
                try: valid=hasher.verify(user['password'] if user else dummy,body.password)
                except VerifyMismatchError: valid=False
                if not valid or not user:
                    failures.append(time.monotonic()); log(c,'Неудачный вход',result='denied')
                else:
                    failures.clear(); token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                    c.execute(sessions.insert().values(id=hashlib.sha256(token.encode()).hexdigest(),csrf=csrf,seen=now())); log(c,'Вход')
                    response.set_cookie('session',token,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=1800)
                    return {'csrf':csrf,'must_change':bool(user['must_change'])}
        raise HTTPException(401,'Неверный пароль')

    @app.get('/api/auth/me')
    def me(request:Request):
        user=auth(request,True); return {'csrf':user['csrf'],'must_change':user['must_change']}

    @app.post('/api/auth/password')
    def change_password(body:ChangePassword,request:Request,response:Response):
        auth(request,True)
        with engine.begin() as c:
            user=c.execute(select(users)).mappings().one()
            try: hasher.verify(user['password'],body.current)
            except VerifyMismatchError: raise HTTPException(400,'Текущий пароль неверен')
            if body.current==body.password: raise HTTPException(400,'Новый пароль должен отличаться')
            c.execute(users.update().where(users.c.id==1).values(password=hasher.hash(body.password),must_change=0)); c.execute(delete(sessions)); log(c,'Смена пароля')
        request.state.refresh_session=None;response.delete_cookie('session'); return {'ok':True}

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response):
        user=auth(request,True)
        with engine.begin() as c: c.execute(delete(sessions).where(sessions.c.id==user['id'])); log(c,'Выход')
        request.state.refresh_session=None;response.delete_cookie('session'); return {'ok':True}

    @app.get('/api/schema',dependencies=[Depends(authorized)])
    def schemas(): return {**{k:model.model_json_schema() for k,model in MODELS.items()},'settings':Settings.model_json_schema()}

    @app.get('/api/openapi.json',dependencies=[Depends(authorized)])
    def openapi(): return app.openapi()

    @app.get('/api/data',dependencies=[Depends(authorized)])
    def master_data():
        with engine.connect() as c: data,revision=get_data(c)
        return {'data':data,'revision':revision,'readiness':prepare_errors(data)}

    @app.post('/api/data/{kind}',dependencies=[Depends(authorized)])
    def write_record(kind:str,body:DataWrite):
        if kind not in MODELS: raise HTTPException(404,'Справочник не найден')
        try: record=MODELS[kind].model_validate(body.record).model_dump(mode='json')
        except ValidationError as exc: raise HTTPException(422,'; '.join(e['message'] for e in validation_errors(exc.errors())))
        with engine.begin() as c:
            data,revision=get_data(c)
            old=next((r for r in data[kind] if r['id']==record['id']),None)
            data[kind]=[r for r in data[kind] if r['id']!=record['id']]+[record]
            errors=validate_data(data)
            if errors: raise HTTPException(422,errors)
            if not save_data(c,data,body.revision): raise HTTPException(409,'Данные уже изменены. Обновите страницу')
            log(c,'Изменение справочника',entity=kind,entity_id=record['id'],old=old,new=record)
        return {'revision':revision+1}

    @app.put('/api/settings',dependencies=[Depends(authorized)])
    def settings(body:SettingsWrite):
        with engine.begin() as c:
            data,revision=get_data(c); old=data['settings']; data['settings']=body.settings.model_dump(mode='json')
            errors=validate_data(data)
            if errors: raise HTTPException(422,errors)
            if not save_data(c,data,body.revision): raise HTTPException(409,'Данные уже изменены. Обновите страницу')
            log(c,'Настройки учебного года',old=old,new=data['settings'])
        return {'revision':revision+1}

    @app.post('/api/demo',dependencies=[Depends(authorized)])
    def demo(large:bool=False):
        with engine.begin() as c:
            data,revision=get_data(c)
            if any(data[k] for k in MODELS if k!='rules'): raise HTTPException(409,'Демонстрация доступна только в пустой базе')
            data=demo_data(large)
            if not save_data(c,data,revision): raise HTTPException(409,'Данные уже изменены')
            log(c,'Загрузка демонстрационных данных',large=large)
        return {'revision':revision+1}

    @app.get('/api/demo/scenarios',dependencies=[Depends(authorized)])
    def demo_scenarios(): return catalogue()

    @app.post('/api/demo/workspace',dependencies=[Depends(authorized)])
    def demo_workspace(body:DemoSwitch):
        candidate=None
        if body.scenario:
            try: candidate=scenario_data(body.scenario,body.seed)
            except ValueError as e: raise HTTPException(422,str(e))
        with guard,engine.begin() as c:
            if any(not control['done'] for control in controls.values()): raise HTTPException(409,'Дождитесь завершения расчёта или отмените его перед сменой сценария')
            data,revision=get_data(c)
            if revision!=body.revision: raise HTTPException(409,'Данные изменились. Обновите страницу перед переключением')
            backup=c.execute(select(demo_backup).where(demo_backup.c.id==1)).mappings().first()
            if candidate is not None:
                if not backup: c.execute(demo_backup.insert().values(id=1,payload=data))
                candidate['_demo']={'scenario':body.scenario,'seed':body.seed,'workspace':uid()}
                action='Открытие демонстрационного сценария'
            else:
                if not backup: raise HTTPException(409,'Демонстрационный режим не включён')
                candidate=backup['payload'];c.execute(delete(demo_backup).where(demo_backup.c.id==1))
                action='Возврат к данным школы'
            if not save_data(c,candidate,revision): raise HTTPException(409,'Данные уже изменены')
            log(c,action,scenario=body.scenario,seed=body.seed)
        return {'revision':revision+1}

    def version(c,vid):
        row=c.execute(select(versions).where(versions.c.id==vid)).mappings().first()
        if not row: raise HTTPException(404,'Версия не найдена')
        data,_=get_data(c)
        if row['payload']['snapshot'].get('_demo',{}).get('workspace')!=data.get('_demo',{}).get('workspace'): raise HTTPException(404,'Версия относится к другому рабочему пространству')
        return dict(row)

    @app.post('/api/generate',status_code=202,dependencies=[Depends(authorized)])
    def generate(body:Generate):
        with guard:
            if any(not control['done'] for control in controls.values()): raise HTTPException(409,'Генерация уже выполняется')
            with engine.begin() as c:
                data,revision=get_data(c); previous=[]
                if body.source_id:
                    source=version(c,body.source_id)['payload']; previous=copy.deepcopy(source['lessons'])
                    if source['snapshot']['settings']['bells']!=data['settings']['bells']:
                        raise HTTPException(422,'Сетка звонков изменилась. Создайте новое расписание без исходной версии')
                    if body.repair_resource:
                        field='teacher_id' if body.repair_scope=='teachers' else 'room_id'
                        if not any(r['id']==body.repair_resource for r in data[body.repair_scope]): raise HTTPException(422,'Ресурс ремонта не найден')
                        resource=next(r for r in data[body.repair_scope] if r['id']==body.repair_resource)
                        resource['availability'] += [{'day':d,'slot':s,'value':'unavailable'} for d in body.repair_days for s in range(len(data['settings']['bells']))]
                        affected={l['id'] for l in previous if l['slot']//slot_stride(data) in body.repair_days and any(p[field]==body.repair_resource for p in l['parts'])}
                        extra=int(len(previous)*body.expand_percent/100); unlocked=0
                        for l in previous:
                            if l['id'] in affected:
                                if l['lock']=='locked': raise HTTPException(422,'Снимите ручную блокировку с затронутых занятий перед ремонтом')
                                l['lock']='preferred'
                            elif l['lock']!='locked' and unlocked<extra: l['lock']='preferred'; unlocked+=1
                            else: l['lock']='locked'
                jid=uid(); payload={'status':'running','stage':'Построение модели','snapshot':data,'revision':revision,'request':body.model_dump(),'previous':previous}
                c.execute(jobs.insert().values(id=jid,created=now(),payload=payload)); log(c,'Запуск генерации',entity_id=jid,parameters=body.model_dump())
            control={'cancel':threading.Event(),'solver':None,'done':False}; controls[jid]=control
            def worker():
                try:
                    result=solve(data,body.week,body.seed,body.seconds,previous,control['cancel'],lambda s:control.update(solver=s))
                except Exception:
                    logging.exception('Generation %s',jid); result={'status':'failed','lessons':[],'errors':['Не удалось завершить расчёт. Проверьте данные и повторите запуск.']}
                with engine.begin() as c:
                    if control['cancel'].is_set(): result['status']='cancelled'
                    c.execute(jobs.update().where(jobs.c.id==jid).values(payload={**payload,**result,'stage':'Завершено'})); log(c,'Завершение генерации',entity_id=jid,result=result['status'])
                with guard: control['done']=True;controls.pop(jid,None)
            pool.submit(worker)
        return {'id':jid}

    @app.get('/api/jobs/{jid}',dependencies=[Depends(authorized)])
    def job(jid:str):
        with engine.connect() as c:
            row=c.execute(select(jobs).where(jobs.c.id==jid)).mappings().first()
            if not row: raise HTTPException(404,'Расчёт не найден')
            p=row['payload']
            if p.get('missing') and 'capacity_issues' not in p:
                week=p['request']['week'];missing=set(p['missing'])
                p={**p,'capacity_issues':capacity_issues(p['snapshot'],week),'diagnostics':diagnose(p['snapshot'],[e for e in events(p['snapshot'],week) if e['id'] in missing],week)}
            return {'id':jid,'created':row['created'],**{k:v for k,v in p.items() if k not in ['snapshot','previous']}}

    @app.post('/api/jobs/{jid}/cancel',dependencies=[Depends(authorized)])
    def cancel(jid:str):
        control=controls.get(jid)
        if control and not control['done']:
            control['cancel'].set()
            if control['solver']: control['solver'].stop_search()
        return {'ok':True}

    @app.post('/api/jobs/{jid}/accept',status_code=201,dependencies=[Depends(authorized)])
    def accept(jid:str):
        with guard,engine.begin() as c:
            row=c.execute(select(jobs).where(jobs.c.id==jid)).mappings().first()
            if not row: raise HTTPException(404,'Расчёт не найден')
            p=row['payload']
            if p.get('accepted_id'): return {'id':p['accepted_id']}
            if p['status'] not in ['complete','partial']: raise HTTPException(422,'Нет результата для сохранения')
            _,revision=get_data(c)
            if p['revision']!=revision: raise HTTPException(409,'Исходные данные изменились. Повторите расчёт')
            vid=uid(); request=p['request']
            lessons=copy.deepcopy(p['lessons'])
            if request['repair_resource']:
                # Repair-only locks must not become permanent user locks.
                source=version(c,request['source_id'])['payload']; locks={l['id']:l['lock'] for l in source['lessons']}
                for l in lessons: l['lock']=locks.get(l['id'],'free'); l['origin']='replacement'
            content={'snapshot':p['snapshot'],'revision':revision,'week':request['week'],'lessons':lessons,'quality':p['quality'],'job_id':jid,'parent_id':request['source_id'],'complete':p['status']=='complete','proposal':p.get('proposal')}
            c.execute(versions.insert().values(id=vid,created=now(),status='draft',payload=content)); c.execute(jobs.update().where(jobs.c.id==jid).values(payload={**p,'accepted_id':vid})); log(c,'Сохранение результата',version=vid,entity_id=jid)
        return {'id':vid}

    @app.post('/api/jobs/{jid}/recommendations',dependencies=[Depends(authorized)])
    def verified_recommendations(jid:str):
        with engine.connect() as c:
            row=c.execute(select(jobs).where(jobs.c.id==jid)).mappings().first()
            if not row: raise HTTPException(404,'Расчёт не найден')
            p=row['payload'];_,revision=get_data(c)
        if p['status'] in ['running','cancelled','failed'] or p['revision']!=revision: raise HTTPException(409,'Завершите или повторите расчёт перед проверкой вариантов')
        baseline=coverage(p['snapshot'],p.get('lessons',[]),p['request']['week']);results=[]
        for proposal in proposals(p['snapshot'],p['request']['week']):
            candidate=proposal['data'];result=solve(candidate,p['request']['week'],p['request']['seed'],2,previous=p.get('previous'))
            gain=coverage(candidate,result['lessons'],p['request']['week'])-baseline
            if gain<=0 or result['errors']:continue
            rid=uid();payload={**p,**result,'snapshot':candidate,'proposal':{'title':proposal['title'],'changes':proposal['changes'],'additional_class_hours':gain,'parent_job':jid}}
            payload.pop('accepted_id',None)
            with engine.begin() as c:
                c.execute(jobs.insert().values(id=rid,created=now(),payload=payload));log(c,'Проверка рекомендации',entity_id=rid,proposal=payload['proposal'],result=result['status'])
            results.append({'id':rid,**payload['proposal'],'status':result['status'],'penalty':result['quality']['penalty']})
        return {'items':results,'message':'Показаны только проверенные варианты, размещающие дополнительные занятия.' if results else 'За время проверки улучшение не найдено. Проверьте доступность, учебный план и блокировки.'}

    @app.get('/api/versions',dependencies=[Depends(authorized)])
    def list_versions():
        with engine.connect() as c:
            data,_=get_data(c); workspace=data.get('_demo',{}).get('workspace')
            return [{'id':r['id'],'created':r['created'],'status':r['status'],'week':r['payload']['week'],'count':len(r['payload']['lessons']),'complete':r['payload']['complete']} for r in c.execute(select(versions).order_by(versions.c.created.desc())).mappings() if r['payload']['snapshot'].get('_demo',{}).get('workspace')==workspace]

    @app.get('/api/versions/{vid}',dependencies=[Depends(authorized)])
    def get_version(vid:str):
        with engine.connect() as c: row=version(c,vid)
        return {'id':vid,'created':row['created'],'status':row['status'],**row['payload'],'events':events(row['payload']['snapshot'],row['payload']['week'])}

    def check_edit(c,vid,body):
        row=version(c,vid); p=row['payload']; lessons=[l.model_dump() for l in body.lessons]
        locked={l['id']:l for l in p['lessons'] if l['lock']=='locked' and next((x['lock'] for x in lessons if x['id']==l['id']),'locked')=='locked'}
        errors=validate_schedule(p['snapshot'],lessons,p['week'],p['complete'],locked)
        if errors: raise HTTPException(422,errors)
        return row,lessons,score(p['snapshot'],lessons,p['week'])

    @app.post('/api/versions/{vid}/validate',dependencies=[Depends(authorized)])
    def validate_edit(vid:str,body:Edit):
        with engine.connect() as c: _,_,quality=check_edit(c,vid,body)
        return {'valid':True,'quality':quality}

    @app.post('/api/versions/{vid}/edit',status_code=201,dependencies=[Depends(authorized)])
    def edit(vid:str,body:Edit):
        with engine.begin() as c:
            row,lessons,quality=check_edit(c,vid,body); new_id=uid()
            content={**row['payload'],'lessons':lessons,'quality':quality,'parent_id':vid}
            c.execute(versions.insert().values(id=new_id,created=now(),status='draft',payload=content)); log(c,'Ручное редактирование',version=new_id,old=vid,new=lessons)
        return {'id':new_id}

    @app.post('/api/versions/{vid}/status',dependencies=[Depends(authorized)])
    def change_status(vid:str,body:StatusChange):
        transitions={'draft':['review','archived'],'review':['approved','draft','archived'],'approved':['published','archived'],'published':['archived'],'archived':[]}
        with guard,engine.begin() as c:
            row=version(c,vid); p=row['payload']
            if body.status not in transitions[row['status']]: raise HTTPException(422,'Недопустимый переход статуса')
            if body.status in ['review','approved','published']:
                current,revision=get_data(c)
                if revision!=p['revision'] and current!=p['snapshot']: raise HTTPException(409,'Исходные данные изменились. Сформируйте новую версию')
                errors=prepare_errors(p['snapshot'])+validate_schedule(p['snapshot'],p['lessons'],p['week'],True)
                if errors: raise HTTPException(422,errors)
            c.execute(versions.update().where(versions.c.id==vid).values(status=body.status)); log(c,'Изменение статуса',version=vid,old=row['status'],new=body.status)
        return {'ok':True}

    @app.post('/api/versions/{vid}/restore',status_code=201,dependencies=[Depends(authorized)])
    def restore(vid:str):
        with engine.begin() as c:
            row=version(c,vid); new_id=uid(); c.execute(versions.insert().values(id=new_id,created=now(),status='draft',payload={**row['payload'],'parent_id':vid})); log(c,'Восстановление версии',version=new_id,old=vid)
        return {'id':new_id}

    @app.get('/api/compare',dependencies=[Depends(authorized)])
    def compare(before:str,after:str):
        with engine.connect() as c: a=version(c,before)['payload']; b=version(c,after)['payload']
        aa={l['id']:l for l in a['lessons']}; bb={l['id']:l for l in b['lessons']}
        def description(version,l):
            ix=indexes(version['snapshot']);e=next(e for e in events(version['snapshot'],version['week']) if e['id']==l['id'])
            stride=slot_stride(version['snapshot']);position=DAYS[l['slot']//stride]+' · '+bell_label(version['snapshot'],l['slot']%stride)
            return ', '.join(ix['classes'][cid]['name'] for cid in e['class_ids'])+' · '+ix['subjects'][e['subject_id']]['name']+' · '+ '; '.join(ix['teachers'][p['teacher_id']]['name']+' / '+ix['rooms'][p['room_id']]['name'] for p in l['parts'])+' · '+position
        return {'added':[{**bb[k],'label':description(b,bb[k])} for k in bb.keys()-aa.keys()],'removed':[{**aa[k],'label':description(a,aa[k])} for k in aa.keys()-bb.keys()], 'changed':[{'before':aa[k],'after':bb[k],'before_label':description(a,aa[k]),'after_label':description(b,bb[k])} for k in aa.keys()&bb.keys() if aa[k]!=bb[k]]}

    @app.get('/api/versions/{vid}/export/{fmt}',dependencies=[Depends(authorized)])
    def download(vid:str,fmt:Literal['csv','xlsx','pdf'],class_id:str='',teacher_id:str='',room_id:str='',subject_id:str='',language:str=''):
        with engine.begin() as c:
            row=version(c,vid)
            filters={'class_id':class_id,'teacher_id':teacher_id,'room_id':room_id,'subject_id':subject_id,'language':language}
            try: content,mime=export(row['payload'],vid,row['status'],fmt,filters)
            except ValueError as e: raise HTTPException(422,str(e))
            log(c,'Экспорт',version=vid,format=fmt,filters=filters)
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="schedule-{vid[:8]}.{fmt}"'})

    @app.get('/api/audit',dependencies=[Depends(authorized)])
    def journal(offset:int=0):
        if offset<0: raise HTTPException(422,'Некорректная страница')
        with engine.connect() as c: return [dict(r) for r in c.execute(select(audit).order_by(audit.c.created.desc()).offset(offset).limit(100)).mappings()]

    if Path('dist/assets').exists(): app.mount('/assets',StaticFiles(directory='dist/assets'),name='assets')
    @app.get('/')
    def frontend():
        if not Path('dist/index.html').exists(): return JSONResponse({'message':'Соберите интерфейс: npm run build'},503)
        return FileResponse('dist/index.html')
    return app

app=create_app()
