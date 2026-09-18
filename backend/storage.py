import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, JSON, Text, select
from .domain import empty_data

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
metadata=MetaData()
state=Table('school_state',metadata,Column('id',Integer,primary_key=True),Column('revision',Integer,nullable=False),Column('payload',JSON,nullable=False))
users=Table('admin_user',metadata,Column('id',Integer,primary_key=True),Column('password',Text,nullable=False),Column('must_change',Integer,nullable=False))
sessions=Table('sessions',metadata,Column('id',String(64),primary_key=True),Column('csrf',String(64),nullable=False),Column('seen',String(40),nullable=False))
versions=Table('versions',metadata,Column('id',String(40),primary_key=True),Column('created',String(40),nullable=False),Column('status',String(30),nullable=False),Column('payload',JSON,nullable=False))
audit=Table('audit',metadata,Column('id',String(40),primary_key=True),Column('created',String(40),nullable=False),Column('action',String(100),nullable=False),Column('payload',JSON,nullable=False))
jobs=Table('jobs',metadata,Column('id',String(40),primary_key=True),Column('created',String(40),nullable=False),Column('payload',JSON,nullable=False))
demo_backup=Table('demo_backup',metadata,Column('id',Integer,primary_key=True),Column('payload',JSON,nullable=False))

def make_engine(url=None):
    Path('data').mkdir(exist_ok=True)
    url=url or os.getenv('DATABASE_URL','sqlite:///data/school.db')
    engine=create_engine(url,connect_args={'check_same_thread':False,'timeout':30} if url.startswith('sqlite') else {})
    metadata.create_all(engine)
    with engine.begin() as c:
        if not c.execute(select(state)).first(): c.execute(state.insert().values(id=1,revision=0,payload=empty_data()))
    return engine

def log(c,action,**payload):
    c.execute(audit.insert().values(id=uid(),created=now(),action=action,payload={'user':'Администратор','correlation_id':uid(),'result':'success',**payload}))

def get_data(c):
    row=c.execute(select(state).where(state.c.id==1)).mappings().one()
    return row['payload'],row['revision']

def save_data(c,data,revision):
    result=c.execute(state.update().where(state.c.id==1,state.c.revision==revision).values(payload=data,revision=revision+1))
    return result.rowcount==1
