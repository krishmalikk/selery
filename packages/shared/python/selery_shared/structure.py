"""Causal descriptive market structure. Heuristic zones are not institutional-flow evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo
from .models import IndicatorPoint

def structure_levels(bars,window=3):
    result={key:[] for key in ('support','resistance','prior_day_high','prior_day_low','opening_range_high','opening_range_low','bullish_gap_lower','bullish_gap_upper')}
    support=resistance=prior_high=prior_low=None
    session=None;day_high=day_low=None;opening=[]
    for i,b in enumerate(bars):
        local=datetime.fromtimestamp(b.time,ZoneInfo('America/New_York'))
        if session!=local.date():
            prior_high,prior_low=day_high,day_low;day_high=day_low=None;opening=[];session=local.date()
        regular=(local.hour,local.minute)>=(9,30) and local.hour<16
        if regular:
            day_high=b.high if day_high is None else max(day_high,b.high)
            day_low=b.low if day_low is None else min(day_low,b.low)
            if (local.hour,local.minute)<(10,0):opening.append(b)
        if i>=window*2:
            candidate=bars[i-window];neighbors=bars[i-window*2:i+1]
            # The pivot is only available at the confirmation bar, never backdated.
            if candidate.low==min(x.low for x in neighbors):support=candidate.low
            if candidate.high==max(x.high for x in neighbors):resistance=candidate.high
        levels={'support':support,'resistance':resistance,'prior_day_high':prior_high,'prior_day_low':prior_low,'opening_range_high':max((x.high for x in opening),default=None) if (local.hour,local.minute)>=(10,0) else None,'opening_range_low':min((x.low for x in opening),default=None) if (local.hour,local.minute)>=(10,0) else None,'bullish_gap_lower':bars[i-2].high if i>=2 and b.low>bars[i-2].high else None,'bullish_gap_upper':b.low if i>=2 and b.low>bars[i-2].high else None}
        for key,value in levels.items():result[key].append(IndicatorPoint(time=b.time,value=value))
    return result
