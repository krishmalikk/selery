import { createChart, CandlestickSeries, LineSeries, createSeriesMarkers, ColorType, CrosshairMode, type UTCTimestamp } from 'lightweight-charts';
import type { ChartResponse, Signal } from './contracts';
import { tokens } from './tokens';

/** DOM renderer shared by desktop and the locally bundled mobile WebView. No data fetching or quant math. */
export function createSeleryChart(container:HTMLElement,data:ChartResponse,onSignal:(signal:Signal)=>void){
  const c=tokens.color;
  const chart=createChart(container,{autoSize:true,layout:{background:{type:ColorType.Solid,color:c.background},textColor:c.muted,fontFamily:'Inter, sans-serif',attributionLogo:true},grid:{vertLines:{color:'#18231d'},horzLines:{color:'#18231d'}},crosshair:{mode:CrosshairMode.Normal},rightPriceScale:{borderColor:c.border},timeScale:{borderColor:c.border,timeVisible:data.timeframe!=='1D'&&data.timeframe!=='1W'},handleScale:{pinch:true,mouseWheel:true,axisPressedMouseMove:true},handleScroll:{horzTouchDrag:true,vertTouchDrag:false,mouseWheel:true,pressedMouseMove:true}});
  const candles=chart.addSeries(CandlestickSeries,{upColor:c.accent,downColor:c.negative,borderVisible:false,wickUpColor:c.accent,wickDownColor:c.negative});
  candles.setData(data.bars.map(b=>({time:b.time as UTCTimestamp,open:b.open,high:b.high,low:b.low,close:b.close})));
  for(const [key,color] of [['ema9',c.accent],['ema21',c.warning],['vwap','#96b6d2']] as const){
    const points=data.indicators[key];if(!points)continue;
    const line=chart.addSeries(LineSeries,{color,lineWidth:1,priceLineVisible:false,lastValueVisible:false,title:key.toUpperCase()});
    line.setData(points.filter(p=>p.value!==null).map(p=>({time:p.time as UTCTimestamp,value:p.value!})));
  }
  if(data.indicators.rsi14){
    const rsi=chart.addSeries(LineSeries,{color:'#9d99bd',lineWidth:1,priceLineVisible:false,lastValueVisible:true,title:'RSI 14'},1);
    rsi.setData(data.indicators.rsi14.filter(p=>p.value!==null).map(p=>({time:p.time as UTCTimestamp,value:p.value!})));
    rsi.createPriceLine({price:70,color:'#574d3d',lineWidth:1,lineStyle:2,axisLabelVisible:false});
    rsi.createPriceLine({price:30,color:'#574d3d',lineWidth:1,lineStyle:2,axisLabelVisible:false});
    chart.panes()[1]?.setHeight(100);
  }
  createSeriesMarkers(candles,data.signals.map(s=>({id:s.id,time:s.time as UTCTimestamp,position:s.direction==='bullish'?'belowBar':'aboveBar',shape:s.direction==='bullish'?'arrowUp':'arrowDown',color:s.direction==='bullish'?c.accent:c.negative,text:''})));
  const find=(time:unknown)=>data.signals.find(s=>s.time===time);
  chart.subscribeClick(p=>{const signal=find(p.time);if(signal)onSignal(signal);});
  let lastSignal:string|null=null;
  chart.subscribeCrosshairMove(p=>{if(!p.hoveredObjectId)return;const signal=data.signals.find(s=>s.id===p.hoveredObjectId);if(signal&&lastSignal!==signal.id){lastSignal=signal.id;onSignal(signal);}});
  let timer:ReturnType<typeof setTimeout>|undefined;
  const touch=(event:TouchEvent)=>{if(event.touches.length!==1)return;const x=event.touches[0].clientX-container.getBoundingClientRect().left;timer=setTimeout(()=>{const signal=find(chart.timeScale().coordinateToTime(x));if(signal)onSignal(signal);},450);};
  const cancel=()=>{if(timer)clearTimeout(timer);};
  container.addEventListener('touchstart',touch,{passive:true});container.addEventListener('touchend',cancel);container.addEventListener('touchmove',cancel);
  chart.timeScale().fitContent();
  return {chart, destroy(){cancel();container.removeEventListener('touchstart',touch);container.removeEventListener('touchend',cancel);container.removeEventListener('touchmove',cancel);chart.remove();}};
}
