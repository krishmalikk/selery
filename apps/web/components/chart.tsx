'use client';
import {useEffect,useRef} from 'react';
import {type ChartResponse,type Signal} from '@selery/shared';
import {createSeleryChart} from '@selery/shared/src/chart';
export default function ResearchChart({data,onSignal,replay,showEma=true}:{data:ChartResponse;onSignal:(s:Signal)=>void;replay:number;showEma?:boolean}){
 const container=useRef<HTMLDivElement>(null);const callback=useRef(onSignal);callback.current=onSignal;
 useEffect(()=>{if(!container.current)return;
 const bars=data.bars.slice(0,replay||data.bars.length),cutoff=bars.at(-1)?.time||0;
 const indicators=Object.fromEntries(Object.entries(data.indicators).filter(([key])=>showEma||!key.includes('ema')).map(([key,points])=>[key,points.filter(p=>p.time<=cutoff)]));
 const renderer=createSeleryChart(container.current,{...data,bars,indicators,signals:data.signals.filter(s=>s.time<=cutoff)},s=>callback.current(s));
 return()=>renderer.destroy();},[data,replay,showEma]);
 return <div className="chart-canvas" ref={container} aria-label={`${data.symbol} candlestick chart with EMA and RSI. Signal details are also available in the list below.`}/>;
}
