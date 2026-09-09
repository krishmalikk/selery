export const disclaimer = 'Selery is research software that displays analysis. It does not execute, recommend, or place trades.';
export const tokens = {
  color: { background:'#0c100f', surface:'#131a17', raised:'#1b2520', border:'#28372e', text:'#e8eee9', muted:'#8d9e93', accent:'#a7c9a0', negative:'#d48984', warning:'#d7b777' },
  font: { sans:'Inter', mono:'JetBrains Mono' },
  space: { xs:4, sm:8, md:16, lg:24, xl:32 },
};
export const watchlist = ['SPY','QQQ','AAPL','NVDA'] as const;
export const timeframes = ['1m','5m','15m','1h','4h','1D','1W'] as const;
export const formatPrice = (value:number|null|undefined) => value == null ? '—' : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(value);
export const formatPercent = (value:number|null|undefined) => value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
export const formatTime = (value:string|number) => new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZone:'America/New_York'}).format(new Date(typeof value==='number'?value*1000:value));
export const feedLabel = (feed:string) => feed==='iex'?'IEX only':feed==='sip'?'SIP consolidated':feed==='synthetic'?'Synthetic fixture':'Delayed / limited';
