"""Deterministic statistics for a bar-aligned, fixed-reference research index."""
from __future__ import annotations
from math import ceil,sqrt
import numpy as np
from scipy.stats import norm


def finite_array(values):
    array=np.asarray(values,dtype=float)
    if array.ndim!=1 or not np.all(np.isfinite(array)):raise ValueError('Statistics require a finite one-dimensional series')
    return array


def index_curve(returns):
    """Additive one-reference-unit index, not compounded account wealth."""
    return np.r_[1.,1+np.cumsum(finite_array(returns))]


def descriptive_stats(returns,*,periods_per_year: int | None=None) -> dict[str,float | None]:
    r=finite_array(returns);n=len(r)
    result={name:None for name in ('sharpe','sortino','calmar','max_drawdown','underwater_fraction','longest_underwater_bars','cvar_95','profit_factor','expectancy_percent','annualized_reference_return_percent')}
    if not n:return result
    curve=index_curve(r);peaks=np.maximum.accumulate(curve)
    # A nonpositive index invalidates percentage drawdowns and annual ratios.
    if np.min(curve)>0:
        drawdown=curve/peaks-1
        result['max_drawdown']=float(drawdown.min()*100)
        underwater=drawdown[1:]<0
        result['underwater_fraction']=float(underwater.mean());longest=current=0
        for below in underwater:
            current=current+1 if below else 0;longest=max(longest,current)
        result['longest_underwater_bars']=float(longest)
    result['expectancy_percent']=float(np.mean(r)*100)
    losses=-float(r[r<0].sum());gains=float(r[r>0].sum())
    result['profit_factor']=gains/losses if losses>0 else None
    if n>=20:result['cvar_95']=float(np.mean(np.sort(r)[:ceil(n*.05)])*100)
    if periods_per_year and n>=periods_per_year and np.min(curve)>0:
        standard=float(np.std(r,ddof=1));downside=float(np.sqrt(np.mean(np.minimum(r,0)**2)))
        annual=float(np.mean(r)*periods_per_year)
        result['annualized_reference_return_percent']=annual*100
        result['sharpe']=float(np.mean(r)/standard*sqrt(periods_per_year)) if standard>1e-15 else None
        result['sortino']=float(np.mean(r)/downside*sqrt(periods_per_year)) if downside>1e-15 else None
        # Fixed-reference additive index: annualized arithmetic return, not CAGR.
        if result['max_drawdown'] and result['max_drawdown']<0:result['calmar']=annual/abs(result['max_drawdown']/100)
    return result


def block_bootstrap_ci(returns,*,samples=1000,seed=42):
    r=finite_array(returns);n=len(r)
    if n<60:return None
    rng=np.random.default_rng(seed);block=max(2,int(sqrt(n)));blocks=ceil(n/block)
    starts=rng.integers(0,n,size=(samples,blocks))
    indices=(starts[:,:,None]+np.arange(block))%n
    means=np.mean(r[indices.reshape(samples,-1)[:,:n]],axis=1)
    return tuple(float(x*100) for x in np.quantile(means,[.025,.975]))


def circular_shift_pvalue(exposure,price_changes,costs,*,samples=1000,seed=42):
    """Descriptive alignment null; preserves serial structure by circular shifts."""
    x=finite_array(exposure);r=finite_array(price_changes);c=finite_array(costs)
    if len(x)!=len(r) or len(r)!=len(c):raise ValueError('Null study series must align')
    n=len(r)
    if n<60 or np.count_nonzero(x)<20 or np.std(x)==0:return None
    rng=np.random.default_rng(seed);observed=float(np.mean(x*r-c))
    shifts=rng.integers(1,n,size=samples)
    null=np.array([np.mean(np.roll(x,int(shift))*r-c) for shift in shifts])
    return float((1+np.sum(null>=observed))/(samples+1))


def deflated_sharpe(returns,trial_sharpes,*,registry_complete=False):
    """Bailey/López de Prado DSR using unannualized trial Sharpes.

    Missing/incomplete trial history is not replaced by an assumed trial count.
    """
    r=finite_array(returns)
    if not registry_complete or trial_sharpes is None:return None,'Complete parameter-trial registry and comparable per-period Sharpes are required'
    trials=finite_array(trial_sharpes)
    if len(r)<252 or len(trials)<2:return None,'At least 252 intervals and two fully recorded comparable trials are required'
    std=float(np.std(r,ddof=1));trial_std=float(np.std(trials,ddof=1))
    if std<=1e-15 or trial_std<=1e-15:return None,'Return and cross-trial dispersion must be nonzero'
    n=len(trials);gamma=.5772156649015329
    expected=trial_std*((1-gamma)*norm.ppf(1-1/n)+gamma*norm.ppf(1-1/(n*np.e)))
    centered=r-np.mean(r);population_std=float(np.std(r))
    skew=float(np.mean((centered/population_std)**3));kurt=float(np.mean((centered/population_std)**4));sr=float(np.mean(r)/std)
    variance=1-skew*sr+(kurt-1)/4*sr*sr
    if variance<=0:return None,'Non-normal Sharpe variance estimate is invalid'
    probability=float(norm.cdf((sr-expected)*sqrt(len(r)-1)/sqrt(variance)))
    return probability,None


def regime_stats(returns,prices):
    r=finite_array(returns);p=finite_array(prices)
    if len(p)!=len(r)+1:raise ValueError('Prices must include the initial baseline observation')
    if len(r)<315:return {},'Regime comparison needs at least 315 daily intervals and 30 observations per cohort'
    benchmark=np.diff(p)/p[:-1];groups={'uptrend':[],'downtrend':[],'high_volatility':[],'low_volatility':[]}
    vol=np.array([np.std(benchmark[i-20:i+1],ddof=1) if i>=20 else np.nan for i in range(len(r))])
    for i in range(252,len(r)):
        groups['uptrend' if p[i]>=p[i-63] else 'downtrend'].append(r[i])
        # The interval-i return cannot enter the regime label used for interval i.
        groups['high_volatility' if vol[i-1]>=np.nanmedian(vol[i-252:i]) else 'low_volatility'].append(r[i])
    result={}
    for name,values in groups.items():
        result[name+'_intervals']=float(len(values))
        result[name+'_mean_percent']=float(np.mean(values)*100) if len(values)>=30 else None
    return result,'Regimes use only prior prices; cohort means are descriptive, not independent discoveries'
