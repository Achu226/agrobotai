import React, { useCallback, useEffect, useState } from 'react';
import { Bug, Cpu, LogOut, RefreshCw, ShieldCheck, Users, Wifi, WifiOff } from 'lucide-react';

// Administrator view of the laptop website (open http://localhost:8000/#admin).
// Signs in with an admin account (created with manage_users.py) and shows who is logged in.
const TOKEN_KEY = 'agrobot_admin_token';

const fmt = (iso) => {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
};

const ago = (iso) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 90) return `${Math.round(s)} s ago`;
  if (s < 5400) return `${Math.round(s / 60)} min ago`;
  if (s < 172800) return `${(s / 3600).toFixed(1)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
};

// Confirmed diseases/pests of the last 30 days from real scans, laptop and Pi combined (uncertain scans are not counted).
function OutbreakSection({ sources, th, td, onExport }) {
  const conditions = {};
  const places = {};
  const used = [];
  for (const [name, o] of sources) {
    if (!o) continue;
    used.push(name);
    for (const c of o.by_condition || []) {
      const row = (conditions[c.label] ||= { label: c.label, kind: c.kind, count: 0, last: c.last_seen, places: new Set(), servers: new Set() });
      row.count += c.count;
      row.last = c.last_seen > row.last ? c.last_seen : row.last;
      c.places.forEach((p) => row.places.add(p));
      row.servers.add(name);
    }
    for (const p of o.by_location || []) {
      const key = `${p.location}|${p.label}`;
      (places[key] ||= { ...p, count: 0 }).count += p.count;
    }
  }
  const rows = Object.values(conditions).sort((a, b) => b.count - a.count);
  const placeRows = Object.values(places).sort((a, b) => a.location.localeCompare(b.location) || b.count - a.count);
  return (
    <div className="card-section" style={{ overflowX: 'auto' }}>
      <div className="section-title"><Bug size={18} /> Disease & pest outbreaks <span style={{ color: '#64748b', fontSize: 13, fontWeight: 400 }}>· last 30 days · confirmed scans only · {used.join(' + ') || 'no data'}</span>
        {rows.length > 0 && <button type="button" className="btn-secondary" style={{ marginLeft: 12 }} onClick={onExport}>Excel file (this server)</button>}
      </div>
      {rows.length === 0 ? <p style={{ margin: 0, color: '#64748b' }}>No confirmed disease or pest in the last 30 days.</p> : (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 14 }}>
            <thead><tr>{['Condition', 'Type', 'Confirmed scans', 'Villages / places', 'Last seen', 'Server'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <td style={td}><b>{r.label}</b></td>
                  <td style={td}>{r.kind}</td>
                  <td style={td}><span style={{ display: 'inline-block', minWidth: 28, padding: '2px 8px', borderRadius: 999, background: r.count >= 5 ? '#fee2e2' : '#fef3c7', fontWeight: 700 }}>{r.count}</span></td>
                  <td style={td}>{[...r.places].join(', ')}</td>
                  <td style={td}>{ago(r.last)}</td>
                  <td style={td}>{[...r.servers].join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>{['Village / place', 'Condition', 'Confirmed scans'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
            <tbody>{placeRows.map((p) => <tr key={`${p.location}|${p.label}`}><td style={td}>{p.location}</td><td style={td}>{p.label}</td><td style={td}>{p.count}</td></tr>)}</tbody>
          </table>
        </>
      )}
    </div>
  );
}

// Raspberry Pi server: live health and its own logins, fetched through the laptop (/api/v1/admin/pi).
function PiSection({ pi, th, td }) {
  if (!pi.ok) {
    return (
      <div className="card-section">
        <div className="section-title"><Cpu size={18} /> Raspberry Pi <span style={{ color: '#b91c1c', fontSize: 14 }}>· offline</span></div>
        <p style={{ color: '#b91c1c', margin: 0 }}>{pi.error}</p>
      </div>
    );
  }
  const d = pi.device || {};
  const power = d.power;
  const up = d.uptime_s;
  const tiles = [
    ['CPU temperature', d.cpu_temp_c != null ? `${d.cpu_temp_c} °C` : '—', d.cpu_temp_c >= 80],
    ['Power', power ? (power.under_voltage_now ? 'Low voltage!' : power.under_voltage_since_boot ? 'Dipped since start' : 'OK') : '—',
      power?.under_voltage_now || power?.under_voltage_since_boot],
    ['Memory used', d.memory_used_pct != null ? `${Math.round(d.memory_used_pct)}%` : '—', d.memory_used_pct >= 90],
    ['Storage free', `${d.disk_free_gb} of ${d.disk_total_gb} GB`, d.disk_free_gb < 1],
    ['Running for', up != null ? `${Math.floor(up / 3600)} h ${Math.floor((up % 3600) / 60)} min` : '—', false],
    ['Scans on Pi', pi.stats?.successful_scans ?? '—', false],
  ];
  const sessions = pi.sessions || [];
  return (
    <div className="card-section" style={{ overflowX: 'auto' }}>
      <div className="section-title"><Cpu size={18} /> Raspberry Pi <span style={{ color: '#047857', fontSize: 14 }}>· online</span>
        <span style={{ color: '#64748b', fontSize: 13, fontWeight: 400 }}> {d.device} · {pi.url}</span></div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        {tiles.map(([label, value, warn]) => (
          <div key={label} style={{ flex: '1 1 140px', padding: 10, borderRadius: 10, background: warn ? '#fef2f2' : '#f0fdf4', textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: warn ? '#b91c1c' : '#0f172a' }}>{value}</div>
            <div style={{ color: '#64748b', fontSize: 13 }}>{label}</div>
          </div>
        ))}
      </div>
      {d.auto_off_idle_hours && <p style={{ color: '#64748b', fontSize: 13, marginTop: 0 }}>Turns off by itself after {d.auto_off_idle_hours} h without use.</p>}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead><tr>{['Status', 'User on Pi', 'Role', 'Device', 'IP address', 'Last seen'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
        <tbody>
          {sessions.length === 0 && <tr><td style={td} colSpan={6}>Nobody is signed in on the Pi.</td></tr>}
          {sessions.map((s, i) => (
            <tr key={i}>
              <td style={td}>{s.online ? <span style={{ color: '#047857', fontWeight: 600 }}><Wifi size={14} /> Online</span> : <span style={{ color: '#94a3b8' }}><WifiOff size={14} /> Idle</span>}</td>
              <td style={td}><b>{s.full_name || s.username}</b><br /><span style={{ color: '#64748b' }}>@{s.username}</span></td>
              <td style={td}>{s.role}</td>
              <td style={td}>{s.device || 'Unknown'}</td>
              <td style={td}>{s.ip || '—'}</td>
              <td style={td}>{ago(s.last_seen)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminPanel({ apiBase }) {
  const [token, setToken] = useState(() => {
    try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
  });
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const api = useCallback(async (path, options = {}) => {
    const res = await fetch(`${apiBase}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', 'X-Client': 'AGROBOTAI web admin', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw Object.assign(new Error(body.detail || `Server error ${res.status}`), { status: res.status });
    return body;
  }, [apiBase, token]);

  // The export needs the login token, so a plain link cannot fetch it: fetch, then hand the browser a temporary link
  const exportOutbreaks = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/v1/admin/outbreaks.csv`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const url = URL.createObjectURL(await res.blob());
      Object.assign(document.createElement('a'), { href: url, download: 'agrobotai_outbreaks.csv' }).click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      window.alert(e.message);
    }
  }, [apiBase, token]);

  const signOut = useCallback(async () => {
    try { if (token) await api('/api/v1/auth/logout', { method: 'POST', body: '{}' }); } catch { /* already gone */ }
    try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
    setToken(null);
    setData(null);
  }, [api, token]);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [sessions, users, stats, pi, outbreaks] = await Promise.all([
        api('/api/v1/admin/sessions'), api('/api/v1/admin/users'), api('/api/v1/admin/stats'),
        // The Pi is optional: its failure must not hide the laptop's own data
        api('/api/v1/admin/pi').catch((e) => ({ configured: true, ok: false, error: e.message })),
        api('/api/v1/admin/outbreaks').catch(() => null),
      ]);
      setData({ ...sessions, users: users.users, stats, pi, outbreaks, loadedAt: new Date() });
      setError(null);
    } catch (e) {
      if (e.status === 401 || e.status === 403) {
        setError(e.status === 403 ? 'This account is not an administrator.' : 'Session expired — please sign in again.');
        try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
        setToken(null);
      } else {
        setError(e.message);
      }
    } finally {
      setLoading(false);
    }
  }, [api, token]);

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);

  const signIn = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const body = await api('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
      if (body.user.role !== 'admin') {
        setError('This account is not an administrator.');
        return;
      }
      try { sessionStorage.setItem(TOKEN_KEY, body.token); } catch { /* storage blocked: stays signed in until reload */ }
      setPassword('');
      setToken(body.token);
    } catch (err) {
      setError(err.message);
    }
  };

  const shell = (children) => (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '1.5rem' }}>
      <div className="agri-header-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <h1 className="agri-app-title" style={{ margin: 0 }}><ShieldCheck size={26} /> Administrator</h1>
        <a href="#" className="btn-secondary" style={{ textDecoration: 'none' }}>← Back to diagnosis</a>
      </div>
      {children}
    </div>
  );

  if (!token) {
    return shell(
      <form className="card-section" onSubmit={signIn} style={{ maxWidth: 420, margin: '2rem auto' }}>
        <div className="section-title">Administrator sign-in</div>
        <label style={{ display: 'block', marginBottom: 8 }}>Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
            style={{ width: '100%', padding: 10, marginTop: 4 }} />
        </label>
        <label style={{ display: 'block', marginBottom: 12 }}>Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required
            style={{ width: '100%', padding: 10, marginTop: 4 }} />
        </label>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        <button className="btn-primary" type="submit" style={{ width: '100%' }}>Sign in</button>
        <p style={{ fontSize: 13, color: '#64748b', marginTop: 12 }}>
          Admin accounts are created on this laptop: <code>.venv\Scripts\python.exe manage_users.py create-admin</code>
        </p>
      </form>,
    );
  }

  const sessions = data?.sessions || [];
  const online = sessions.filter((s) => s.online);
  const th = { textAlign: 'left', padding: '8px 10px', borderBottom: '2px solid #e2e8f0', fontSize: 13, color: '#475569' };
  const td = { padding: '8px 10px', borderBottom: '1px solid #f1f5f9', fontSize: 14, verticalAlign: 'top' };

  return shell(
    <>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '1rem 0' }}>
        {[
          ['Online now', data ? data.online_users : '…'],
          ['Active logins', sessions.length],
          ['Farmers', data?.stats?.farmers ?? '…'],
          ['Scans', data?.stats?.successful_scans ?? '…'],
          ['Pending review', data?.stats?.pending_review ?? '…'],
        ].map(([label, value]) => (
          <div key={label} className="card-section" style={{ flex: '1 1 160px', margin: 0, textAlign: 'center' }}>
            <div style={{ fontSize: 30, fontWeight: 700 }}>{value}</div>
            <div style={{ color: '#64748b' }}>{label}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn-secondary" onClick={load} disabled={loading}><RefreshCw size={16} /> {loading ? 'Refreshing…' : 'Refresh'}</button>
        <button className="btn-secondary" onClick={signOut}><LogOut size={16} /> Sign out</button>
        {data && <span style={{ color: '#64748b', fontSize: 13 }}>Updated {data.loadedAt.toLocaleTimeString()} · refreshes every 15 s · "online" = active in the last 5 minutes</span>}
      </div>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}

      <OutbreakSection sources={[['Laptop', data?.outbreaks], ['Raspberry Pi', data?.pi?.ok ? data.pi.outbreaks : null]]} th={th} td={td} onExport={exportOutbreaks} />

      {data?.pi?.configured && <PiSection pi={data.pi} th={th} td={td} />}

      <div className="card-section" style={{ overflowX: 'auto' }}>
        <div className="section-title"><Wifi size={18} /> Who is logged in ({online.length} online)</div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['Status', 'User', 'Role', 'Device', 'IP address', 'Last seen', 'Signed in'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {sessions.length === 0 && <tr><td style={td} colSpan={7}>Nobody is signed in.</td></tr>}
            {sessions.map((s, i) => (
              <tr key={i}>
                <td style={td}>{s.online
                  ? <span style={{ color: '#047857', fontWeight: 600 }}><Wifi size={14} /> Online</span>
                  : <span style={{ color: '#94a3b8' }}><WifiOff size={14} /> Idle</span>}</td>
                <td style={td}><b>{s.full_name || s.username}</b><br /><span style={{ color: '#64748b' }}>@{s.username}{s.location ? ` · ${s.location}` : ''}</span></td>
                <td style={td}>{s.role}</td>
                <td style={td}>{s.device || 'Unknown (older app)'}</td>
                <td style={td}>{s.ip || '—'}</td>
                <td style={td}>{ago(s.last_seen)}<br /><span style={{ color: '#94a3b8', fontSize: 12 }}>{fmt(s.last_seen)}</span></td>
                <td style={td}>{fmt(s.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card-section" style={{ overflowX: 'auto' }}>
        <div className="section-title"><Users size={18} /> All accounts</div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>{['User', 'Role', 'Farm / location', 'Scans', 'Created'].map((h) => <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {(data?.users || []).map((u) => (
              <tr key={u.id}>
                <td style={td}><b>{u.full_name || u.username}</b><br /><span style={{ color: '#64748b' }}>@{u.username}</span></td>
                <td style={td}>{u.role}{u.is_active ? '' : ' (disabled)'}</td>
                <td style={td}>{[u.farm_name, u.location].filter(Boolean).join(' · ') || '—'}</td>
                <td style={td}>{u.scan_count ?? 0}</td>
                <td style={td}>{fmt(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>,
  );
}
