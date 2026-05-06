import React, { useState, useEffect, useCallback } from 'react';
import UploadZone from './components/UploadZone';
import AuditView from './components/AuditView';
import ReportGen from './components/ReportGen';
import FlaggedQueue from './components/FlaggedQueue';

const API_BASE = 'http://localhost:8000';

const TABS = [
  { id: 'upload', label: 'Upload', icon: '📤' },
  { id: 'results', label: 'Results', icon: '📊' },
  { id: 'review', label: 'Review', icon: '🔍' },
  { id: 'report', label: 'Report', icon: '📄' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [tenders, setTenders] = useState([]);
  const [selectedTenderId, setSelectedTenderId] = useState('');
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [evaluating, setEvaluating] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [selectedBidder, setSelectedBidder] = useState(null);

  // Fetch tender list
  const fetchTenders = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tenders`);
      if (res.ok) {
        const data = await res.json();
        setTenders(data.tenders || []);
      }
    } catch (e) { /* server may be offline */ }
  }, []);

  // Fetch dashboard data for selected tender
  const fetchDashboard = useCallback(async (tid) => {
    if (!tid) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/dashboard/${tid}`);
      if (!res.ok) throw new Error('Failed to load dashboard');
      const data = await res.json();
      setDashboard(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTenders(); }, [fetchTenders]);
  useEffect(() => { if (selectedTenderId) fetchDashboard(selectedTenderId); }, [selectedTenderId, fetchDashboard]);

  const handleTenderUploaded = (data) => {
    setSelectedTenderId(data.tender_id);
    setSuccess(`Tender processed! ID: ${data.tender_id}`);
    fetchTenders();
  };

  const handleBidUploaded = () => {
    setSuccess('Bid document processed successfully');
    if (selectedTenderId) fetchDashboard(selectedTenderId);
  };

  const handleEvaluate = async () => {
    if (!selectedTenderId) return;
    setEvaluating(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/evaluate/${selectedTenderId}`, { method: 'POST' });
      if (!res.ok) throw new Error('Evaluation failed');
      setSuccess('All bids evaluated');
      await fetchDashboard(selectedTenderId);
    } catch (e) { setError(e.message); }
    finally { setEvaluating(false); }
  };

  const handleAudit = async () => {
    if (!selectedTenderId) return;
    setAuditing(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/audit/${selectedTenderId}`);
      if (!res.ok) throw new Error('Audit failed');
      setSuccess('Audit complete');
      await fetchDashboard(selectedTenderId);
    } catch (e) { setError(e.message); }
    finally { setAuditing(false); }
  };

  const evaluations = dashboard?.evaluations || [];
  const audits = dashboard?.audits || [];
  const bidders = dashboard?.bidders || [];
  const flaggedCount = audits.reduce((n, a) => n + (a.flagged_items?.length || 0), 0);

  // Get verdict badge
  const statusBadge = (status) => {
    const map = {
      eligible: { cls: 'badge-eligible', text: '✅ Eligible' },
      not_eligible: { cls: 'badge-not-eligible', text: '❌ Not Eligible' },
      manual_review: { cls: 'badge-review', text: '⚠️ Review' },
    };
    const m = map[status] || { cls: '', text: status || '—' };
    return <span className={`badge ${m.cls}`}>{m.text}</span>;
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="header-brand">
            <div className="header-logo">CT</div>
            <div>
              <div className="header-title">CRPF Tender AI</div>
              <div className="header-subtitle">Multi-Agent Procurement Evaluation</div>
            </div>
          </div>
          <div className="header-status">
            <span className="status-dot"></span> System Online
          </div>
        </div>
      </header>

      {/* Banners */}
      {error && (
        <div className="banner banner-error">
          <span>⚠️</span> {error}
          <button className="banner-close" onClick={() => setError('')}>×</button>
        </div>
      )}
      {success && (
        <div className="banner banner-success">
          <span>✅</span> {success}
          <button className="banner-close" onClick={() => setSuccess('')}>×</button>
        </div>
      )}

      {/* Tender Selector */}
      {tenders.length > 0 && (
        <div className="tender-selector">
          <label>Active Tender:</label>
          <select value={selectedTenderId} onChange={(e) => setSelectedTenderId(e.target.value)}>
            <option value="">Select a tender...</option>
            {tenders.map((t) => (
              <option key={t.tender_id} value={t.tender_id}>
                {t.tender_id} — {t.filename}
              </option>
            ))}
          </select>
          {selectedTenderId && (
            <>
              <button className="btn btn-primary btn-sm" onClick={handleEvaluate} disabled={evaluating}>
                {evaluating ? 'Evaluating...' : '⚡ Evaluate All Bids'}
              </button>
              <button className="btn btn-outline btn-sm" onClick={handleAudit} disabled={auditing}>
                {auditing ? 'Auditing...' : '🔍 Run Audit'}
              </button>
            </>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            {tab.label}
            {tab.id === 'review' && flaggedCount > 0 && (
              <span className="tab-badge">{flaggedCount}</span>
            )}
            {tab.id === 'results' && evaluations.length > 0 && (
              <span className="tab-badge">{evaluations.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <div className="loading-text">Loading dashboard data...</div>
        </div>
      )}

      {/* Tab Content */}
      {!loading && (
        <div className="tab-content">
          {/* UPLOAD TAB */}
          {activeTab === 'upload' && (
            <div className="upload-section">
              <UploadZone type="tender" onUploadComplete={handleTenderUploaded} />
              <UploadZone type="bid" tenderId={selectedTenderId} onUploadComplete={handleBidUploaded}
                disabled={!selectedTenderId} />
            </div>
          )}

          {/* RESULTS TAB */}
          {activeTab === 'results' && (
            <div>
              {evaluations.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon">📊</div>
                  <div className="empty-title">No Evaluations Yet</div>
                  <div className="empty-text">Upload tender & bid documents, then click "Evaluate All Bids"</div>
                </div>
              ) : (
                <>
                  <div className="card" style={{ marginBottom: '24px' }}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Bidder ID</th>
                          <th>Status</th>
                          <th>Criteria Met</th>
                          <th>Rejection Reasons</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluations.map((ev, i) => {
                          const met = (ev.criteria_results || []).filter((c) => c.verdict === 'eligible').length;
                          const total = (ev.criteria_results || []).length;
                          return (
                            <tr key={i}>
                              <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ev.bidder_id}</td>
                              <td>{statusBadge(ev.overall_status)}</td>
                              <td>{met}/{total}</td>
                              <td style={{ fontSize: '0.8rem', maxWidth: '300px' }}>
                                {(ev.rejection_reasons || []).length > 0
                                  ? ev.rejection_reasons.map((r, j) => <div key={j} style={{ color: 'var(--status-not-eligible)', marginBottom: '2px' }}>• {r}</div>)
                                  : <span style={{ color: 'var(--text-muted)' }}>—</span>
                                }
                              </td>
                              <td>
                                <button className="btn btn-outline btn-sm" onClick={() => { setSelectedBidder(ev.bidder_id); }}>
                                  View Details
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* Detail View for selected bidder */}
                  {selectedBidder && (
                    <AuditView
                      evaluation={evaluations.find((e) => e.bidder_id === selectedBidder)}
                      bidderData={bidders.find((b) => b.bidder_id === selectedBidder)}
                    />
                  )}
                </>
              )}
            </div>
          )}

          {/* REVIEW TAB */}
          {activeTab === 'review' && (
            <FlaggedQueue audits={audits} tenderId={selectedTenderId} />
          )}

          {/* REPORT TAB */}
          {activeTab === 'report' && (
            <ReportGen report={dashboard?.report} tenderId={selectedTenderId} evaluations={evaluations} />
          )}
        </div>
      )}
    </div>
  );
}
