import React from 'react';
import { AlertCircle, Clock, TrendingUp, Landmark, ExternalLink, ShieldAlert } from 'lucide-react';

// Parses German-style dates like "25.09.2026" or "17.09.2026 23:59 Ortszeit"
function parseGermanDate(dateStr) {
  if (!dateStr) return null;
  const match = dateStr.match(/(\d{2})\.(\d{2})\.(\d{4})/);
  if (!match) return null;
  const [, day, month, year] = match;
  const parsed = new Date(`${year}-${month}-${day}`);
  return isNaN(parsed.getTime()) ? null : parsed;
}

function daysUntil(dateStr) {
  const deadline = parseGermanDate(dateStr);
  if (!deadline) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diffMs = deadline - today;
  return Math.round(diffMs / (1000 * 60 * 60 * 24));
}

function urgencyColor(days) {
  if (days === null) return '#9ca3af';
  if (days < 0) return '#9ca3af';
  if (days <= 7) return '#dc2626';
  if (days <= 30) return '#d97706';
  return '#16a34a';
}

function urgencyLabel(days) {
  if (days === null) return 'Unknown';
  if (days < 0) return 'Closed';
  if (days === 0) return 'Today';
  if (days === 1) return '1 day left';
  return `${days} days left`;
}

function formatValue(value) {
  if (value === null || value === undefined) return '—';
  return `€${Number(value).toLocaleString('de-DE')}`;
}

function fitTierColor(tier) {
  switch (tier) {
    case 'Great fit': return '#16a34a';
    case 'Good fit': return '#65a30d';
    case 'Partial fit': return '#d97706';
    case 'Low fit': return '#dc2626';
    default: return '#9ca3af';
  }
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div style={{
      flex: 1, padding: '16px 20px', backgroundColor: 'white',
      borderRadius: '12px', border: '1px solid #e5e7eb',
      display: 'flex', alignItems: 'center', gap: '12px'
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: '10px',
        backgroundColor: `${color}1a`, display: 'flex',
        alignItems: 'center', justifyContent: 'center', flexShrink: 0
      }}>
        <Icon size={20} color={color} />
      </div>
      <div>
        <div style={{ fontSize: '22px', fontWeight: 'bold', color: '#111827', lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>{label}</div>
      </div>
    </div>
  );
}

function TenderDashboard({ tenders }) {
  const withDays = (tenders || [])
    .filter(t => t.title !== 'Required')
    .map(t => ({ ...t, _daysLeft: daysUntil(t.submissionDeadline) }))
    .sort((a, b) => {
      if (a._daysLeft === null) return 1;
      if (b._daysLeft === null) return -1;
      return a._daysLeft - b._daysLeft;
    });

  const closingThisWeek = withDays.filter(t => t._daysLeft !== null && t._daysLeft >= 0 && t._daysLeft <= 7).length;
  const totalValue = withDays.reduce((sum, t) => sum + (Number(t.estimatedValue) || 0), 0);

  if (withDays.length === 0) {
    return (
      <div style={{ flex: 1, padding: '40px', textAlign: 'center', color: '#9ca3af' }}>
        No tenders to show yet. Try searching for something in the sidebar.
      </div>
    );
  }

  return (
    <div style={{ flex: 1, padding: '24px', overflowY: 'auto', backgroundColor: '#f9fafb', height: '100vh', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
        <StatCard icon={TrendingUp} label="Tenders shown" value={withDays.length} color="#7c3aed" />
        <StatCard icon={AlertCircle} label="Closing within 7 days" value={closingThisWeek} color="#dc2626" />
        <StatCard icon={Clock} label="Total estimated value" value={formatValue(totalValue)} color="#16a34a" />
      </div>

      <div style={{ backgroundColor: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Deadline</th>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Tender</th>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Authority</th>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Sector</th>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Fit</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}>Value</th>
              <th style={{ textAlign: 'center', padding: '12px 16px', color: '#6b7280', fontWeight: 600 }}></th>
            </tr>
          </thead>
          <tbody>
            {withDays.map((t, i) => (
              <tr key={i} style={{ borderBottom: i < withDays.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
                <td style={{ padding: '14px 16px' }}>
                  <span style={{
                    display: 'inline-block', padding: '4px 10px', borderRadius: '999px',
                    backgroundColor: `${urgencyColor(t._daysLeft)}1a`,
                    color: urgencyColor(t._daysLeft), fontWeight: 600, fontSize: '12px',
                    whiteSpace: 'nowrap'
                  }}>
                    {urgencyLabel(t._daysLeft)}
                  </span>
                </td>
                                <td style={{ padding: '14px 16px', maxWidth: '320px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <div style={{ fontWeight: 500, color: '#111827' }}>{t.title}</div>
                    {t.factsVerified === false && (
                      <span
                        title={`Fact-check could not confirm this tender's details against the source text:\n${(t.factCheckNotes || []).join('\n')}`}
                        style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
                      >
                        <ShieldAlert size={15} color="#dc2626" />
                      </span>
                    )}
                  </div>
                  {t.referenceNumber && (
                    <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>{t.referenceNumber}</div>
                  )}
                </td>
                <td style={{ padding: '14px 16px', color: '#4b5563' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Landmark size={13} color="#9ca3af" />
                    {t.contractingAuthority || '—'}
                  </div>
                </td>
                <td style={{ padding: '14px 16px', color: '#4b5563' }}>{t.sector || '—'}</td>
                <td style={{ padding: '14px 16px' }}>
                  {t.fitTier && (
                    <span style={{
                      display: 'inline-block', padding: '4px 10px', borderRadius: '999px',
                      backgroundColor: `${fitTierColor(t.fitTier)}1a`,
                      color: fitTierColor(t.fitTier), fontWeight: 600, fontSize: '12px',
                      whiteSpace: 'nowrap'
                    }}
                    title={(t.fitReasons || []).map(r => `${r.status}: ${r.criterion} — ${r.reason}`).join('\n')}
                    >
                      {t.fitTier}
                    </span>
                  )}
                </td>
                <td style={{ padding: '14px 16px', textAlign: 'right', color: '#111827', fontWeight: 500 }}>
                  {formatValue(t.estimatedValue)}
                </td>
                <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                  {t.url && (
                    <a href={t.url} target="_blank" rel="noreferrer" style={{ color: '#7c3aed' }}>
                      <ExternalLink size={15} />
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default TenderDashboard;