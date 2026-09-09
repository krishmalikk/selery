"""Durable research records with immutable signal snapshots and atomic budget reservations."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,MetaData,Table,Column,String,JSON,DateTime,Float,Integer,select,update,insert
from sqlalchemy.exc import IntegrityError

metadata=MetaData()
COLLECTIONS=('signals','outcomes','journal','alerts','reports','jobs','audit','models','features','news','devices','settings')
tables={name:Table(name,metadata,Column('id',String,primary_key=True),Column('created_at',DateTime(timezone=True),nullable=False),Column('payload',JSON,nullable=False)) for name in COLLECTIONS}
budgets=Table('budgets',metadata,Column('month',String,primary_key=True),Column('spent',Float,nullable=False,default=0),Column('reserved',Float,nullable=False,default=0))
bars_table=Table('bars',metadata,Column('symbol',String,primary_key=True),Column('feed',String,primary_key=True),Column('timeframe',String,primary_key=True),Column('time',DateTime(timezone=True),primary_key=True),Column('available_at',DateTime(timezone=True),nullable=False),Column('open',Float),Column('high',Float),Column('low',Float),Column('close',Float),Column('volume',Float),Column('source',String),Column('version',String,nullable=False,default='1'))

def serial(value):
    if hasattr(value,'model_dump'):return value.model_dump(mode='json')
    return json.loads(json.dumps(value,default=str))

class Store:
    def __init__(self,url):
        if url.startswith('sqlite:///') and ':memory:' not in url:Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True,exist_ok=True)
        kwargs={'connect_args':{'check_same_thread':False}} if url.startswith('sqlite') else {'pool_pre_ping':True}
        if ':memory:' in url:
            from sqlalchemy.pool import StaticPool
            kwargs['poolclass']=StaticPool
        self.engine=create_engine(url,**kwargs)
        metadata.create_all(self.engine)

    def put(self,collection,payload,id=None,immutable=False):
        id=id or uuid4().hex
        table=tables[collection]
        payload=serial(payload)
        with self.engine.begin() as conn:
            existing=conn.execute(select(table.c.payload).where(table.c.id==id)).first()
            if existing:
                if immutable:return id
                conn.execute(update(table).where(table.c.id==id).values(payload=payload))
            else:
                conn.execute(insert(table).values(id=id,created_at=datetime.now(timezone.utc),payload=payload))
        return id

    def get(self,collection,id):
        table=tables[collection]
        with self.engine.connect() as conn:
            row=conn.execute(select(table.c.payload).where(table.c.id==id)).first()
            return row[0] if row else None

    def list(self,collection,limit=200,offset=0):
        table=tables[collection]
        with self.engine.connect() as conn:
            return [r[0] for r in conn.execute(select(table.c.payload).order_by(table.c.created_at.desc()).limit(limit).offset(offset))]

    def audit(self,event,detail):
        self.put('audit',{'event':event,'detail':serial(detail),'timestamp':datetime.now(timezone.utc).isoformat()})

    def reserve(self,amount,cap):
        if amount<=0 or cap<=0:return False
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        try:
            with self.engine.begin() as conn:conn.execute(insert(budgets).values(month=month,spent=0,reserved=0))
        except IntegrityError:pass
        with self.engine.begin() as conn:
            result=conn.execute(update(budgets).where(budgets.c.month==month,budgets.c.spent+budgets.c.reserved+amount<=cap).values(reserved=budgets.c.reserved+amount))
            return result.rowcount==1

    def settle(self,reserved,actual):
        if not 0<=actual<=reserved:raise ValueError('Actual usage exceeds reserved maximum; disable provider until reconciled.')
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        with self.engine.begin() as conn:
            result=conn.execute(update(budgets).where(budgets.c.month==month,budgets.c.reserved>=reserved).values(reserved=budgets.c.reserved-reserved,spent=budgets.c.spent+actual))
            if result.rowcount!=1:raise ValueError('Budget reservation not found')

    def spend(self):
        month=datetime.now(timezone.utc).strftime('%Y-%m')
        with self.engine.connect() as conn:
            row=conn.execute(select(budgets.c.spent,budgets.c.reserved).where(budgets.c.month==month)).first()
            return float(sum(row)) if row else 0.0
