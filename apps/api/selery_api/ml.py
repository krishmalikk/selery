"""Point-in-time meta-labeling research. Training is manual; no prediction without validation."""
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import brier_score_loss,roc_auc_score
from sklearn.calibration import calibration_curve
from selery_shared.indicators import ema,rsi,atr
from .outcomes import score_signal

VERSION='meta-labels-1'

def fractional_difference(values,d=0.4,window=30):
    """Fixed-width fractional differentiation; each output reads only its prefix."""
    if not 0<d<1 or window<2:raise ValueError('d must be between zero and one; window >= 2')
    weights=[1.0]
    for k in range(1,window):weights.append(-weights[-1]*(d-k+1)/k)
    output=np.full(len(values),np.nan)
    for i in range(window-1,len(values)):output[i]=np.dot(weights,np.asarray(values[i-window+1:i+1])[::-1])
    return output

def feature_rows(bars):
    """No normalization is fitted here. Raw causal features carry availability timestamps."""
    close=[b.close for b in bars];fast=ema(close,9);slow=ema(close,21);strength=rsi(close);volatility=atr(bars);frac=fractional_difference(close)
    rows={}
    for i,b in enumerate(bars):
        if not b.finalized or i<30:continue
        values=[(fast[i]-slow[i])/b.close,strength[i]/100,volatility[i]/b.close,close[i]/close[i-5]-1,float(frac[i])/b.close]
        if all(np.isfinite(values)):rows[b.time]={'available_at':b.available_at,'features':values}
    return rows

def meta_dataset(signals,bars):
    rows=feature_rows(bars);x=[];y=[];start=[];end=[]
    for signal in signals:
        row=rows.get(signal.time)
        if not row or row['available_at']>signal.available_at:continue
        outcome=score_signal(signal,bars)
        if outcome.status not in ('target_first','stop_first','neither'):continue
        future=[b for b in bars if b.finalized and b.time>=signal.available_at]
        label_end=outcome.resolved_at or (future[signal.horizon_bars-1].available_at if len(future)>=signal.horizon_bars else None)
        if label_end is None:continue
        x.append(row['features']+[1.0 if signal.direction=='bullish' else -1.0]);y.append(int(outcome.status=='target_first'));start.append(signal.available_at);end.append(label_end)
    return np.asarray(x,dtype=float),np.asarray(y,dtype=int),np.asarray(start),np.asarray(end)

def purged_walk_forward(starts,ends,n_splits=3,embargo_seconds=86400):
    """Expanding past-only training; purge all labels that reach the validation boundary."""
    starts=np.asarray(starts);ends=np.asarray(ends)
    if len(starts)!=len(ends) or np.any(ends<starts) or np.any(np.diff(starts)<0):raise ValueError('Events must be ordered with valid label intervals')
    chunks=np.array_split(np.arange(len(starts)),n_splits+1)
    for validation in chunks[1:]:
        if not len(validation):continue
        cutoff=starts[validation[0]]-embargo_seconds
        train=np.flatnonzero((starts<cutoff)&(ends<cutoff))
        yield train,validation

def reliability(y,probabilities):
    fraction,mean=calibration_curve(y,probabilities,n_bins=5,strategy='quantile')
    return [{'predicted':float(p),'observed':float(f)} for p,f in zip(mean,fraction)]

def train_meta(signals,bars,store,artifact_dir):
    """Fit on past folds only, calibrate on out-of-fold predictions, preserve final holdout."""
    x,y,starts,ends=meta_dataset(signals,bars)
    if len(y)<120 or len(np.unique(y))<2:
        return {'status':'unavailable','reason':f'Need at least 120 complete labeled events across both classes; found {len(y)}. No model was trained.','version':VERSION}
    split=int(len(y)*0.8);hold_start=starts[split]
    development=np.flatnonzero((np.arange(len(y))<split)&(ends<hold_start-86400))
    holdout=np.arange(split,len(y))
    if len(development)<60:return {'status':'unavailable','reason':'Insufficient purged development events.'}
    xdev,ydev,sdev,edev=x[development],y[development],starts[development],ends[development]
    folds=[];oof_prob=[];oof_y=[]
    def complex_model():
        try:
            from lightgbm import LGBMClassifier
            return LGBMClassifier(n_estimators=60,max_depth=3,num_leaves=7,verbosity=-1,random_state=42,n_jobs=1)
        except ImportError:return HistGradientBoostingClassifier(max_iter=60,max_depth=3,random_state=42)
    for train,valid in purged_walk_forward(sdev,edev):
        if len(train)<20 or len(np.unique(ydev[train]))<2:continue
        baseline=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500,random_state=42))
        model=complex_model();baseline.fit(xdev[train],ydev[train]);model.fit(xdev[train],ydev[train])
        base=baseline.predict_proba(xdev[valid])[:,1];probs=model.predict_proba(xdev[valid])[:,1]
        folds.append({'baseline_brier':float(brier_score_loss(ydev[valid],base)),'model_brier':float(brier_score_loss(ydev[valid],probs)),'train_events':len(train),'validation_events':len(valid)})
        oof_prob.extend(probs);oof_y.extend(ydev[valid])
    if len(folds)<3 or len(set(oof_y))<2:return {'status':'unavailable','reason':'Three valid purged folds with both classes were not available.','folds':folds}
    calibrator=LogisticRegression(random_state=42).fit(np.asarray(oof_prob).reshape(-1,1),oof_y)
    model=complex_model().fit(xdev,ydev)
    baseline=make_pipeline(StandardScaler(),LogisticRegression(max_iter=500,random_state=42)).fit(xdev,ydev)
    raw=model.predict_proba(x[holdout])[:,1];probs=calibrator.predict_proba(raw.reshape(-1,1))[:,1]
    base=baseline.predict_proba(x[holdout])[:,1]
    model_score=float(brier_score_loss(y[holdout],probs));baseline_score=float(brier_score_loss(y[holdout],base))
    stable=all(f['model_brier']<=f['baseline_brier'] for f in folds) and model_score<baseline_score
    model_id=uuid4().hex
    result={'id':model_id,'status':'champion' if stable else 'rejected','version':VERSION,'created_at':datetime.now(timezone.utc).isoformat(),'folds':folds,'holdout_brier':model_score,'baseline_holdout_brier':baseline_score,'reliability':reliability(y[holdout],probs),'events':len(y),'holdout_events':len(holdout),'model':type(model).__name__,'reason':'Beat baseline in every fold and final holdout.' if stable else 'Did not beat baseline consistently; no confidence is exposed.','feature_names':['ema_gap','rsi','atr_fraction','lagged_price_change','fractional_difference','signal_direction'],'shap_status':'available with optional SHAP package after promotion'}
    if stable:
        import joblib
        target=Path(artifact_dir);target.mkdir(parents=True,exist_ok=True)
        joblib.dump({'model':model,'baseline':baseline,'calibrator':calibrator,'version':VERSION},target/f'{model_id}.joblib')
    store.put('models',result,model_id);store.audit('manual_model_research',{'id':model_id,'status':result['status']})
    return result

def drift_score(reference,current):
    """Population stability index using bins fixed on the reference sample."""
    reference=np.asarray(reference);current=np.asarray(current)
    edges=np.unique(np.quantile(reference,np.linspace(0,1,6)))
    if len(edges)<3:return None
    edges[0]=-np.inf;edges[-1]=np.inf
    a=np.maximum(np.histogram(reference,edges)[0]/len(reference),1e-6)
    b=np.maximum(np.histogram(current,edges)[0]/len(current),1e-6)
    return float(np.sum((b-a)*np.log(b/a)))

def sequence_model(input_features,kind='lstm'):
    """Optional sequence architecture; the same purged evaluator must qualify it before use."""
    import torch
    from torch import nn
    if kind not in ('lstm','gru','transformer'):raise ValueError('Unknown sequence architecture')
    class SequenceMeta(nn.Module):
        def __init__(self):
            super().__init__()
            self.input=nn.Linear(input_features,32)
            self.encoder=nn.TransformerEncoder(nn.TransformerEncoderLayer(d_model=32,nhead=4,batch_first=True,dropout=0),num_layers=1) if kind=='transformer' else (nn.LSTM if kind=='lstm' else nn.GRU)(32,32,batch_first=True)
            self.head=nn.Linear(32,1)
        def forward(self,x):
            embedded=self.input(x)
            if kind=='transformer':
                length=x.shape[1];mask=torch.triu(torch.ones(length,length,device=x.device,dtype=torch.bool),diagonal=1)
                encoded=self.encoder(embedded,mask=mask)
            else:encoded,_=self.encoder(embedded)
            return self.head(encoded[:,-1]).squeeze(-1)
    return SequenceMeta()
