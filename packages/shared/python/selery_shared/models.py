from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import date,datetime
from enum import StrEnum
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = 'Selery is research software that displays analysis. It does not execute, recommend, or place trades.'

class Feed(StrEnum):
    IEX = 'iex'
    SIP = 'sip'
    DELAYED = 'delayed'
    SYNTHETIC = 'synthetic'

class Timeframe(StrEnum):
    M1 = '1m'
    M5 = '5m'
    M15 = '15m'
    H1 = '1h'
    H4 = '4h'
    D1 = '1D'
    W1 = '1W'

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Provenance(Contract):
    provider: str
    feed: Feed
    observed_at: datetime
    available_at: datetime
    retrieved_at: datetime
    stale: bool = False
    synthetic: bool = False
    version: str = '1'

class Bar(Contract):
    symbol: str
    time: int
    available_at: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    feed: Feed
    finalized: bool = True

class Quote(Contract):
    symbol: str
    price: float
    change: float | None = None
    change_percent: float | None = None
    bid: float | None = None
    ask: float | None = None
    provenance: Provenance
    sparkline: list[float] = Field(default_factory=list)

class IndicatorPoint(Contract):
    time: int
    value: float | None

class Capability(Contract):
    id: str
    label: str
    enabled: bool
    reason: str | None = None

class Signal(Contract):
    id: str
    symbol: str
    strategy: str
    strategy_version: str = '1'
    timeframe: Timeframe
    time: int
    available_at: int
    direction: Literal['bullish', 'bearish']
    reference_price: float
    stop: float
    target: float
    horizon_bars: int = 20
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_reason: str | None = 'No calibrated model is attached to this signal.'
    feed: Feed
    features: dict[str, float] = Field(default_factory=dict)
    explanation: str

class ChartResponse(Contract):
    symbol: str
    timeframe: Timeframe
    bars: list[Bar]
    indicators: dict[str, list[IndicatorPoint]]
    signals: list[Signal]
    capabilities: list[Capability]
    provenance: Provenance

class WatchlistResponse(Contract):
    quotes: list[Quote]
    data_mode: Literal['fixtures', 'live']

class NewsItem(Contract):
    id: str
    headline: str
    summary: str
    url: str
    source: str
    published_at: datetime
    symbols: list[str]
    sentiment: float | None = None
    sentiment_method: str | None = None

class NewsResponse(Contract):
    items: list[NewsItem]
    retrieved_at: datetime
    stale: bool

class Outcome(Contract):
    signal_id: str
    status: Literal['pending', 'target_first', 'stop_first', 'neither', 'ambiguous', 'incomplete']
    evaluated_at: datetime
    bars_observed: int
    resolved_at: int | None = None
    max_favorable_percent: float | None = None
    max_adverse_percent: float | None = None
    reason: str | None = None

class OutcomeSummary(Contract):
    strategy: str
    feed: Feed
    matured: int
    target_first: int
    stop_first: int
    neither: int
    ambiguous: int
    hit_rate: float | None
    denominator: str = 'All matured, complete, unambiguous signals, including neither.'
    historical_hit_rate: float | None = None
    comparison_reason: str | None = None

class SizingRequest(Contract):
    research_capital: float = Field(gt=0)
    risk_percent: float = Field(gt=0, le=5)
    reference_price: float = Field(gt=0)
    stop: float = Field(gt=0)
    max_allocation_percent: float = Field(default=20, gt=0, le=100)

class SizingResponse(Contract):
    units: int
    risk_budget: float
    analytical_risk: float
    notional: float
    disclaimer: str = 'Informational calculation only; no action is taken.'

class JournalEntry(Contract):
    id: str | None = None
    symbol: str = Field(min_length=1, max_length=12)
    thesis: str = Field(min_length=1, max_length=10000)
    outcome: str = Field(default='', max_length=10000)
    reflection: str = Field(default='', max_length=10000)
    chart_snapshot: str | None = Field(default=None, max_length=500000)
    created_at: datetime | None = None

class Alert(Contract):
    id: str
    kind: str
    title: str
    body: str
    symbol: str | None = None
    signal_id: str | None = None
    created_at: datetime
    read: bool = False

class ResearchRequest(Contract):
    symbol: str = 'SPY'
    timeframe: Timeframe = Timeframe.D1
    strategy: str = 'ema_cross'
    feed: Feed = Feed.IEX
    horizon_bars: int = Field(default=20, ge=1, le=252)

class ResearchReport(Contract):
    id: str
    created_at: datetime
    request: ResearchRequest
    signal_count: int
    outcomes: list[Outcome]
    metrics: dict[str, float | None]
    assumptions: list[str]
    limitations: list[str]
    series: list[IndicatorPoint]
    benchmark: list[IndicatorPoint]

class Job(Contract):
    id: str
    kind: str
    status: Literal['queued', 'running', 'completed', 'failed', 'unavailable']
    created_at: datetime
    result_id: str | None = None
    reason: str | None = None

class StrategyInfo(Contract):
    id: str
    name: str
    description: str
    enabled: bool
    reason: str | None = None
    requires: list[str] = Field(default_factory=list)

class ChatRequest(Contract):
    message: str = Field(min_length=1, max_length=4000)
    symbol: str = 'SPY'
    debate: bool = False

class Citation(Contract):
    label: str
    timestamp: datetime
    url: str | None = None
    data_id: str | None = None

class ChatResponse(Contract):
    message: str
    citations: list[Citation]
    mode: Literal['local', 'llm']
    cost_usd: float = 0

class Settings(Contract):
    data_mode: Literal['fixtures', 'live']
    feed: Feed
    llm_monthly_cap_usd: float
    llm_spent_usd: float
    llm_enabled: bool
    disclaimer: str = DISCLAIMER

class DeviceRegistration(Contract):
    token: str = Field(pattern=r'^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$', max_length=230)
    platform: Literal['ios', 'android']
    enabled: bool = True

class DeviceRegistrationResult(Contract):
    id: str
    enabled: bool

class DeliverySummary(Contract):
    accepted: int
    failed: int
    skipped: int
    unknown: int

class DataQuery(Contract):
    provider: Literal['finnhub','alpha_vantage','twelve_data','fred','sec','kenneth_french','yfinance']
    dataset: str = Field(min_length=1,max_length=60)
    symbol: str = 'SPY'
    timeframe: Timeframe = Timeframe.D1
    start: datetime | None = None
    end: datetime | None = None
    series_id: str | None = None
    cik: str | None = None
    as_of: date | None = None
    archive: bool = False

class StreamEvent(Contract):
    type: Literal['quotes', 'chart', 'signal', 'news', 'alert', 'heartbeat', 'error']
    timestamp: datetime
    data: dict

class MarketDataProvider(Protocol):
    async def quotes(self, symbols: list[str]) -> list[Quote]: ...
    async def bars(self, symbol: str, timeframe: Timeframe, feed: Feed, limit: int = 1000) -> list[Bar]: ...
    async def news(self, symbols: list[str]) -> list[NewsItem]: ...

class Strategy(ABC):
    id: str
    version: str = '1'
    required_capabilities: tuple[str, ...] = ()

    @abstractmethod
    def evaluate(self, bars: list[Bar], timeframe: Timeframe) -> list[Signal]:
        """Consume finalized bars only; no data after each signal's available_at."""
        raise NotImplementedError
