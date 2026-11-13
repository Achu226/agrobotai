import React, { useCallback, useEffect, useState } from 'react';
import { CalendarDays, CloudSun, Download, Leaf, LogOut, Megaphone, Package, Sprout, Store, Trash2, Wallet } from 'lucide-react';

// Farmer's own page on the website (open http://localhost:8000/#farm): the same tools as the phone app's
// Weather tab and farm diary. Signs in with the farmer's app account; everything comes from /api/v1.
const TOKEN_KEY = 'agrobot_farmer_token';

const SPRAY_REASONS = {
  dark: 'Night', rain: 'Raining', rain_soon: 'Rain expected within 6 h', windy: 'Too windy (spray drifts)',
  too_calm: 'Air too calm (fine spray drifts)', hot: 'Too hot (spray dries before it works)',
  wind_unknown: 'Wind not known', no_forecast: 'No forecast',
};
const COMMODITIES = {
  Tomato: 'Tomato', Potato: 'Potato', Onion: 'Onion', 'Paddy(Dhan)(Common)': 'Paddy', Banana: 'Banana',
  Brinjal: 'Brinjal', 'Green Chilli': 'Green Chilli', Maize: 'Maize', Coconut: 'Coconut', Grapes: 'Grapes',
};
const KINDS = {
  spray: 'Spray', fertilizer: 'Fertilizer', irrigation: 'Irrigation', sowing: 'Sowing / seed', weeding: 'Weeding',
  harvest: 'Harvest', labour: 'Labour', sale: 'Sale (money received)', note: 'Note',
};

const hour = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
const rs = (v) => `₹${Math.round(v).toLocaleString('en-IN')}`;
const today = () => new Date().toLocaleDateString('sv'); // YYYY-MM-DD in local time
const input = { width: '100%', padding: 10, marginTop: 4, boxSizing: 'border-box' };
const muted = { color: '#64748b', fontSize: 13 };

// Profit per plot: a "sale" amount is money received, every other amount is a cost (same rule as the app).
export function profitByPlot(entries) {
  const rows = {};
  for (const e of entries) {
    if (typeof e.cost !== 'number') continue;
    const r = (rows[e.plot] ||= { spent: 0, earned: 0 });
    if (e.kind === 'sale') r.earned += e.cost; else r.spent += e.cost;
  }
  return rows;
}

function SprayAndWeather({ api, location }) {
  const [place, setPlace] = useState(location || '');
  const [data, setData] = useState(null);
  const load = useCallback(async (p) => {
    setData({ loading: true });
    try {
      const [spray, weather] = await Promise.all([
        api(`/api/v1/spray-plan?location=${encodeURIComponent(p)}`),
        p.trim().length >= 2 ? api(`/api/v1/weather?location=${encodeURIComponent(p)}`) : Promise.resolve(null),
      ]);
      setData({ spray, weather });
    } catch (e) {
      setData({ error: e.message });
    }
  }, [api]);
  useEffect(() => { load(location || ''); }, [load, location]);

  const s = data?.spray;
  const cur = data?.weather?.ok ? data.weather.weather.current : null;
  return (
    <div className="card-section">
      <div className="section-title"><CloudSun size={18} /> Weather & spray planner</div>
      <form onSubmit={(e) => { e.preventDefault(); load(place); }} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Village or town" style={{ ...input, marginTop: 0 }} />
        <button className="btn-primary" type="submit">Check</button>
      </form>
      {data?.loading && <p style={muted}>Loading…</p>}
      {data?.error && <p style={{ color: '#b91c1c' }}>{data.error}</p>}
      {cur && <p style={{ margin: '0 0 10px' }}><b>{cur.temp_c}°C</b> · humidity {cur.humidity}% · wind {cur.wind_kph} km/h · {cur.condition}</p>}
      {s && !s.ok && <p style={{ color: '#b91c1c' }}>{s.error}</p>}
      {s?.ok && (
        <>
          <p style={{ fontSize: 18, fontWeight: 700, color: s.ok_now ? '#15803d' : '#b45309', margin: '0 0 6px' }}>
            {s.ok_now ? '✅ Good time to spray now' : `⚠️ Not now: ${s.now_problems.map((c) => SPRAY_REASONS[c] || c).join(', ')}`}
          </p>
          <p style={{ margin: 0 }}>
            {s.best_window
              ? <>Best window: <b>{hour(s.best_window.start)} – {hour(new Date(new Date(s.best_window.end).getTime() + 3600e3))}</b> ({s.best_window.hours} h)</>
              : 'No safe spraying window in the next 24 h.'}
          </p>
          <p style={muted}>{s.location} · rules: no rain for {s.rules.rain_free_hours} h, wind {s.rules.wind_kph[0]}–{s.rules.wind_kph[1]} km/h, below {s.rules.max_temp_c}°C</p>
        </>
      )}
    </div>
  );
}

const RESULTS = {
  disease_detected: 'Disease found', pest_detected: 'Pest found', disease_and_pest_detected: 'Disease and pest found',
  healthy: 'Healthy', uncertain: 'Not sure', unsupported_crop: 'Not a supported crop',
};

// The farmer's own leaf scans (taken with the phone app), newest first, with the PDF report.
function MyScans({ api, download }) {
  const [scans, setScans] = useState(null);
  useEffect(() => { api('/api/v1/scans?limit=30').then((b) => setScans(b.scans), () => setScans([])); }, [api]);
  const th = { textAlign: 'left', padding: 6, borderBottom: '2px solid #e2e8f0' };
  const td = { padding: 6 };
  return (
    <div className="card-section" style={{ overflowX: 'auto' }}>
      <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span><Leaf size={18} /> My scans</span>
        {scans?.length > 0 && <button type="button" className="btn-secondary" onClick={() => download('/api/v1/export.csv?what=scans', 'agrobotai_scans.csv')}><Download size={14} /> Excel file</button>}
      </div>
      {!scans && <p style={muted}>Loading…</p>}
      {scans?.length === 0 && <p style={muted}>No scans yet. Scan a leaf with the phone app and it appears here.</p>}
      {scans?.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Date', 'Plot', 'Crop', 'Result', 'Affected', ''].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>{scans.map((x) => (
            <tr key={x.id}>
              <td style={td}>{(x.captured_at || x.received_at || '').slice(0, 10)}</td>
              <td style={td}>{x.plot || '—'}</td>
              <td style={td}>{x.crop_reported || x.crop_selected || '—'}</td>
              <td style={td}><b>{[x.disease_state === 'disease_detected' && x.disease_label, x.pest_state === 'pest_detected' && x.pest_label].filter(Boolean).join(' + ') || RESULTS[x.summary_state] || x.summary_state || '—'}</b></td>
              <td style={td}>{typeof x.severity_pct === 'number' ? `${x.severity_pct.toFixed(1)}%` : '—'}</td>
              <td style={td}>{x.inference_status !== 'failed' && <button type="button" className="btn-secondary" onClick={() => download(`/api/v1/scans/${x.id}/report.pdf`, `agrobotai_scan_${x.id}.pdf`)}>PDF</button>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}

// What other farmers' scans confirmed in this farmer's village (counts only). Hidden when the account has no location.
function NearbyAlerts({ api }) {
  const [data, setData] = useState(null);
  useEffect(() => { api('/api/v1/outbreaks/nearby').then(setData, () => setData(null)); }, [api]);
  if (!data?.ok) return null;
  return (
    <div className="card-section">
      <div className="section-title"><Megaphone size={18} /> Disease alerts near {data.location}</div>
      {data.alerts.length === 0
        ? <p style={muted}>No disease or pest was confirmed near {data.location} in the last {data.days} days.</p>
        : (
          <ul style={{ margin: 0 }}>
            {data.alerts.map((a) => (
              <li key={a.label}><b>{a.display_name}</b> <span style={muted}>· {a.kind} · {a.count} confirmed scans · last on {a.last_seen.slice(0, 10)}</span></li>
            ))}
            <li style={muted}>Found by other farmers in the last {data.days} days. Check your crop for the same signs.</li>
          </ul>
        )}
    </div>
  );
}

function MarketPrices({ api }) {
  const [commodity, setCommodity] = useState('Tomato');
  const [data, setData] = useState(null);
  useEffect(() => {
    let live = true;
    setData(null);
    api(`/api/v1/market-prices?commodity=${encodeURIComponent(commodity)}`)
      .then((d) => live && setData(d), (e) => live && setData({ ok: false, error: e.message }));
    return () => { live = false; };
  }, [api, commodity]);
  const rows = data?.records || [];
  return (
    <div className="card-section" style={{ overflowX: 'auto' }}>
      <div className="section-title"><Store size={18} /> Market prices (Tamil Nadu)</div>
      <select value={commodity} onChange={(e) => setCommodity(e.target.value)} style={{ ...input, marginTop: 0, marginBottom: 10 }}>
        {Object.entries(COMMODITIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      {!data && <p style={muted}>Loading…</p>}
      {data && !data.ok && <p style={{ color: '#64748b' }}>{data.error}</p>}
      {data?.ok && rows.length === 0 && <p style={muted}>No prices published today for this crop in Tamil Nadu.</p>}
      {rows.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Market', 'District', 'Variety', 'Date', 'Modal', 'Min–Max'].map((h) => <th key={h} style={{ textAlign: 'left', padding: 6, borderBottom: '2px solid #e2e8f0' }}>{h}</th>)}</tr></thead>
          <tbody>{rows.slice(0, 20).map((r, i) => (
            <tr key={i}>
              <td style={{ padding: 6 }}>{r.market}</td><td style={{ padding: 6 }}>{r.district}</td><td style={{ padding: 6 }}>{r.variety}</td>
              <td style={{ padding: 6 }}>{r.arrival_date}</td><td style={{ padding: 6, fontWeight: 700 }}>{rs(r.modal_price)}</td>
              <td style={{ padding: 6 }}>{rs(r.min_price)}–{rs(r.max_price)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {data?.ok && <p style={muted}>Price per quintal (100 kg). Source: Agmarknet, Government of India.</p>}
    </div>
  );
}

function FertilizerCalculator({ api }) {
  const [f, setF] = useState({ n: '', p2o5: '', k2o: '', acres: '1', dose_per: 'acre' });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const calc = async (e) => {
    e.preventDefault();
    const q = new URLSearchParams({ n: f.n || '0', p2o5: f.p2o5 || '0', k2o: f.k2o || '0', acres: f.acres, dose_per: f.dose_per });
    try {
      setResult(await api(`/api/v1/fertilizer?${q}`));
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  };
  return (
    <div className="card-section">
      <div className="section-title"><Package size={18} /> Fertilizer bag calculator</div>
      <p style={muted}>Type the N-P-K (kg) from your Soil Health Card or agriculture officer.</p>
      <form onSubmit={calc} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8, alignItems: 'end' }}>
        {[['n', 'N (kg)'], ['p2o5', 'P₂O₅ (kg)'], ['k2o', 'K₂O (kg)']].map(([k, label]) => (
          <label key={k}>{label}<input type="number" min="0" step="any" value={f[k]} onChange={set(k)} style={input} /></label>
        ))}
        <label>Dose is<select value={f.dose_per} onChange={set('dose_per')} style={input}><option value="acre">kg per acre</option><option value="hectare">kg per hectare</option></select></label>
        <label>Field size (acres)<input type="number" min="0.01" step="any" required value={f.acres} onChange={set('acres')} style={input} /></label>
        <button className="btn-primary" type="submit">Calculate bags</button>
      </form>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {result && (
        <ul style={{ marginTop: 12 }}>
          {result.items.filter((i) => i.kg > 0).map((i) => (
            <li key={i.product}><b>{i.product}: buy {i.bags_to_buy} bags</b> <span style={muted}>({i.kg} kg = {i.bags} × {i.bag_kg} kg · {i.gives})</span></li>
          ))}
          {result.extra_n_kg > 0 && <li style={{ color: '#b45309' }}>DAP already gives {result.extra_n_kg} kg more nitrogen than asked, so no urea is needed.</li>}
          <li style={muted}>All phosphorus from DAP, potash from MOP. Split urea into 2–3 doses as your officer advises.</li>
        </ul>
      )}
    </div>
  );
}

function CropCalendar({ api }) {
  const [crops, setCrops] = useState([]);
  const [f, setF] = useState({ crop: '', plot: '', sown_on: new Date().toISOString().slice(0, 10) });
  const [plan, setPlan] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => { api('/api/v1/calendar').then((b) => setCrops(b.crops), () => setCrops([])); }, [api]);
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPlan(null); setMsg(null); };
  const show = async (e) => {
    e.preventDefault();
    try { setPlan(await api(`/api/v1/calendar?${new URLSearchParams({ crop: f.crop, sown_on: f.sown_on })}`)); setMsg(null); } catch (err) { setMsg(err.message); }
  };
  const save = async () => {
    try {
      const r = await api('/api/v1/calendar', { method: 'POST', body: JSON.stringify(f) });
      setMsg(`${r.entries.length} reminders saved to the farm diary (the phone app reminds you on each date).`);
    } catch (err) { setMsg(err.message); }
  };
  return (
    <div className="card-section">
      <div className="section-title"><CalendarDays size={18} /> Crop calendar</div>
      <form onSubmit={show} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 8, alignItems: 'end' }}>
        <label>Crop<select required value={f.crop} onChange={set('crop')} style={input}><option value="">Choose…</option>{crops.map((c) => <option key={c}>{c}</option>)}</select></label>
        <label>Sowing / transplanting date<input type="date" required value={f.sown_on} onChange={set('sown_on')} style={input} /></label>
        <label>Plot / field name<input maxLength={60} value={f.plot} onChange={set('plot')} style={input} /></label>
        <button className="btn-primary" type="submit">Show calendar</button>
      </form>
      {plan && (
        <>
          <p style={muted}>{plan.note} Harvest around <b>{plan.harvest_on}</b>.</p>
          <ul>{plan.tasks.map((t, i) => <li key={i}><b>{t.date}</b> (day {t.day}) — {t.task}</li>)}</ul>
          <button className="btn-secondary" disabled={!f.plot.trim()} onClick={save}>{f.plot.trim() ? 'Save as diary reminders' : 'Type a plot name to save'}</button>
        </>
      )}
      {msg && <p style={{ marginTop: 8 }}>{msg}</p>}
    </div>
  );
}

function ProfitBook({ api, download }) {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ plot: '', kind: 'sale', product: '', cost: '', done_on: today() });
  const load = useCallback(() => api('/api/v1/diary').then((b) => setEntries(b.entries), (e) => setError(e.message)), [api]);
  useEffect(() => { load(); }, [load]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const add = async (e) => {
    e.preventDefault();
    try {
      await api('/api/v1/diary', { method: 'POST', body: JSON.stringify({ ...form, cost: form.cost === '' ? null : Number(form.cost) }) });
      setForm({ ...form, product: '', cost: '' });
      setError(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  };
  const remove = async (id) => {
    if (!window.confirm('Delete this diary entry?')) return;
    try { await api(`/api/v1/diary/${id}`, { method: 'DELETE' }); } catch (err) { setError(err.message); }
    load();
  };
  const rows = profitByPlot(entries || []);
  const total = Object.values(rows).reduce((a, r) => ({ spent: a.spent + r.spent, earned: a.earned + r.earned }), { spent: 0, earned: 0 });
  const money = entries ? entries.filter((x) => typeof x.cost === 'number') : [];
  const profitCell = (r) => {
    const p = r.earned - r.spent;
    return <td style={{ padding: 6, fontWeight: 700, color: p < 0 ? '#b91c1c' : '#15803d' }}>{p < 0 ? '−' : ''}{rs(Math.abs(p))}</td>;
  };
  return (
    <div className="card-section" style={{ overflowX: 'auto' }}>
      <div className="section-title" style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <span><Wallet size={18} /> Profit & expenses</span>
        {entries?.length > 0 && <button type="button" className="btn-secondary" onClick={() => download('/api/v1/export.csv?what=diary', 'agrobotai_diary.csv')}><Download size={14} /> Excel file</button>}
      </div>
      <form onSubmit={add} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8, alignItems: 'end', marginBottom: 14 }}>
        <label>Plot<input required maxLength={60} value={form.plot} onChange={set('plot')} style={input} /></label>
        <label>What<select value={form.kind} onChange={set('kind')} style={input}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
        <label>Item / note<input maxLength={80} value={form.product} onChange={set('product')} style={input} /></label>
        <label>{form.kind === 'sale' ? 'Amount received (₹)' : 'Cost (₹)'}<input type="number" min="0" step="any" value={form.cost} onChange={set('cost')} style={input} /></label>
        <label>Date<input type="date" required value={form.done_on} onChange={set('done_on')} style={input} /></label>
        <button className="btn-primary" type="submit">Add</button>
      </form>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {!entries && !error && <p style={muted}>Loading…</p>}
      {entries && Object.keys(rows).length === 0 && <p style={muted}>No costs or sales yet. Add what you spent (seed, spray, labour…) and what you sold.</p>}
      {Object.keys(rows).length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 14 }}>
          <thead><tr>{['Plot', 'Spent', 'Earned', 'Profit'].map((h) => <th key={h} style={{ textAlign: 'left', padding: 6, borderBottom: '2px solid #e2e8f0' }}>{h}</th>)}</tr></thead>
          <tbody>
            {Object.entries(rows).map(([plot, r]) => <tr key={plot}><td style={{ padding: 6 }}>{plot}</td><td style={{ padding: 6 }}>{rs(r.spent)}</td><td style={{ padding: 6 }}>{rs(r.earned)}</td>{profitCell(r)}</tr>)}
            {Object.keys(rows).length > 1 && <tr style={{ borderTop: '2px solid #e2e8f0' }}><td style={{ padding: 6 }}><b>All plots</b></td><td style={{ padding: 6 }}>{rs(total.spent)}</td><td style={{ padding: 6 }}>{rs(total.earned)}</td>{profitCell(total)}</tr>}
          </tbody>
        </table>
      )}
      {money.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Date', 'Plot', 'What', 'Item', 'Amount', ''].map((h) => <th key={h} style={{ textAlign: 'left', padding: 6, borderBottom: '1px solid #e2e8f0', fontSize: 13 }}>{h}</th>)}</tr></thead>
          <tbody>{money.map((x) => (
            <tr key={x.id}>
              <td style={{ padding: 6 }}>{x.done_on}</td><td style={{ padding: 6 }}>{x.plot}</td><td style={{ padding: 6 }}>{KINDS[x.kind] || x.kind}</td>
              <td style={{ padding: 6 }}>{x.product || x.note || ''}</td>
              <td style={{ padding: 6, color: x.kind === 'sale' ? '#15803d' : undefined }}>{x.kind === 'sale' ? '+' : ''}{rs(x.cost)}</td>
              <td style={{ padding: 6 }}><button type="button" className="btn-secondary" aria-label="Delete entry" onClick={() => remove(x.id)}><Trash2 size={14} /></button></td>
            </tr>
          ))}</tbody>
        </table>
      )}
      <p style={muted}>Profit = money from sales − all costs written in the diary. The phone app's farm diary shows the same entries.</p>
    </div>
  );
}

export default function FarmerPanel({ apiBase }) {
  const [token, setToken] = useState(() => {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
  });
  const [user, setUser] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const api = useCallback(async (path, options = {}) => {
    const res = await fetch(`${apiBase}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', 'X-Client': 'AGROBOTAI website', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    });
    const body = await res.json().catch(() => ({}));
    if (res.status === 401 && token) {
      try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
      setToken(null);
    }
    if (!res.ok) throw Object.assign(new Error(typeof body.detail === 'string' ? body.detail : `Server error ${res.status}`), { status: res.status });
    return body;
  }, [apiBase, token]);

  // Files need the login token, so a plain link cannot fetch them: fetch, then hand the browser a temporary link
  const download = useCallback(async (path, filename) => {
    try {
      const res = await fetch(`${apiBase}${path}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const url = URL.createObjectURL(await res.blob());
      Object.assign(document.createElement('a'), { href: url, download: filename }).click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      window.alert(e.message);
    }
  }, [apiBase, token]);

  useEffect(() => {
    if (token) api('/api/v1/auth/me').then((b) => setUser(b.user || b), () => setUser(null));
  }, [api, token]);

  const signIn = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const body = await api('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      try { sessionStorage.setItem(TOKEN_KEY, body.token); } catch { /* storage blocked: stays signed in until reload */ }
      setPassword('');
      setUser(body.user);
      setToken(body.token);
    } catch (err) {
      setError(err.message);
    }
  };

  const signOut = async () => {
    try { await api('/api/v1/auth/logout', { method: 'POST', body: '{}' }); } catch { /* already gone */ }
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
    setToken(null);
    setUser(null);
  };

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '1.5rem' }}>
      <div className="agri-header-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <h1 className="agri-app-title" style={{ margin: 0 }}><Sprout size={26} /> My farm{user ? ` · ${user.full_name || user.username}` : ''}</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <a href="#" className="btn-secondary" style={{ textDecoration: 'none' }}>← Back to diagnosis</a>
          {token && <button className="btn-secondary" onClick={signOut}><LogOut size={14} /> Sign out</button>}
        </div>
      </div>
      {!token ? (
        <form className="card-section" onSubmit={signIn} style={{ maxWidth: 420, margin: '2rem auto' }}>
          <div className="section-title">Sign in with your AGROBOTAI app account</div>
          <label style={{ display: 'block', marginBottom: 8 }}>Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required style={input} />
          </label>
          <label style={{ display: 'block', marginBottom: 12 }}>Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required style={input} />
          </label>
          {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
          <button className="btn-primary" type="submit" style={{ width: '100%' }}>Sign in</button>
          <p style={muted}>No account? Create one in the phone app (Register), then sign in here.</p>
        </form>
      ) : (
        <>
          <NearbyAlerts api={api} />
          <SprayAndWeather api={api} location={user?.location || ''} />
          <MarketPrices api={api} />
          <FertilizerCalculator api={api} />
          <CropCalendar api={api} />
          <MyScans api={api} download={download} />
          <ProfitBook api={api} download={download} />
        </>
      )}
    </div>
  );
}
