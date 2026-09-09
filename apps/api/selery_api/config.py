import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[3]
load_dotenv(ROOT/'.env')

@dataclass(frozen=True)
class Config:
    endpoint: str
    key: str
    secret: str
    password: str
    session_secret: str
    data_mode: str
    database_url: str
    allowed_origins: tuple[str,...]
    llm_cap: float

    @classmethod
    def load(cls):
        endpoint=os.getenv('ALPACA_ENDPOINT','')
        parsed=urlparse(endpoint)
        if parsed.scheme!='https' or parsed.hostname!='paper-api.alpaca.markets' or parsed.username or parsed.password or parsed.port:
            raise RuntimeError('ALPACA_ENDPOINT must use the HTTPS paper host; startup refused.')
        mode=os.getenv('SELERY_DATA_MODE','fixtures')
        if mode not in ('fixtures','live'):raise RuntimeError('SELERY_DATA_MODE must be fixtures or live')
        password=os.getenv('SELERY_PASSWORD','')
        session_secret=os.getenv('SELERY_SESSION_SECRET','')
        if len(password)<12 or len(session_secret)<32:
            raise RuntimeError('Set SELERY_PASSWORD (12+ characters) and SELERY_SESSION_SECRET (32+ characters).')
        return cls(endpoint,os.getenv('ALPACA_KEY',''),os.getenv('ALPACA_SECRET',''),password,session_secret,mode,
                   os.getenv('SELERY_DATABASE_URL','sqlite:///./data/selery.db'),
                   tuple(os.getenv('SELERY_ALLOWED_ORIGINS','http://localhost:3000').split(',')),
                   max(0,float(os.getenv('SELERY_LLM_MONTHLY_CAP_USD','0'))))
