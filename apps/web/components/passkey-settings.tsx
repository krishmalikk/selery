"use client";
import {useEffect, useState, type FormEvent} from 'react';
import {SeleryClient, type PasskeyInfo, type PasskeyStatus} from '@selery/shared';
import {registerPasskey, supportsPasskeys} from './passkeys';

export function PasskeySettings({api, onChanged}: {api: SeleryClient; onChanged: () => void}) {
  const [items, setItems] = useState<PasskeyInfo[]>([]);
  const [status, setStatus] = useState<PasskeyStatus | null>(null);
  const [password, setPassword] = useState(''), [name, setName] = useState('My Mac');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  useEffect(() => {let alive = true;
    Promise.all([api.passkeyStatus(), api.passkeys()]).then(([s, keys]) => {if (alive) {setStatus(s);setItems(keys);}})
      .catch(() => {if (alive) setMessage('Passkey settings could not be loaded.');});
    return () => {alive = false;};
  }, [api]);
  async function enroll(e: FormEvent) {
    e.preventDefault();setBusy(true);setMessage('');
    const entered = password;setPassword('');
    try {
      await registerPasskey(api, entered, name.trim() || 'My passkey');
      setItems(await api.passkeys());onChanged();
      setMessage('Passkey saved. Next time, choose Open workspace and unlock with your device.');
    } catch (error) {setMessage(error instanceof Error ? error.message : 'Could not save the passkey.');}
    finally {setBusy(false);}
  }
  async function remove(item: PasskeyInfo) {
    if (!confirm(`Remove ${item.name}? Sessions opened with this passkey will also end. Your workspace password remains available.`)) return;
    setBusy(true);setMessage('');
    try {await api.removePasskey(item.id);setItems(await api.passkeys());onChanged();setMessage('Passkey removed.');}
    catch {setMessage('Passkey removed or session expired. If settings no longer load, sign in with your password.');}
    finally {setBusy(false);}
  }
  return <section className="panel padded">
    <h2>Touch ID &amp; passkeys</h2>
    <p className="muted">Set up once with your workspace password. Your browser can then unlock Selery with Touch ID, Face ID, or your device’s passkey unlock. Selery never receives your fingerprint.</p>
    {!status ? <p className="muted">Loading passkey settings…</p> : !status.enabled ? <p className="notice">{status.reason}</p> :
      !supportsPasskeys() ? <p className="notice">Use a supported browser on HTTPS to add a passkey.</p> :
      <form onSubmit={enroll} style={{maxWidth: 380, margin: '16px 0'}}>
        <label htmlFor="passkey-name">Passkey name</label>
        <input id="passkey-name" value={name} maxLength={80} onChange={e => setName(e.target.value)} required disabled={busy}/>
        <label htmlFor="passkey-password">Confirm workspace password for setup</label>
        <input id="passkey-password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required disabled={busy}/>
        <button className="primary" disabled={busy || !password} style={{marginTop:12}}>{busy ? 'Waiting for your device…' : 'Enable Touch ID / passkey'}</button>
      </form>}
    {items.map(item => <div key={item.id} className="section-title" style={{gap:16}}><span>{item.name}</span><button disabled={busy} onClick={() => void remove(item)}>Remove passkey</button></div>)}
    {!!message && <p role="status" className="notice">{message}</p>}
    <p className="muted small">Keep the password for recovery. Your browser controls whether it offers biometrics or a device PIN.</p>
  </section>;
}
