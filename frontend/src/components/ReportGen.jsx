import React, { useState } from 'react';

/**
 * ReportGen — Final report viewer with download and summary stats.
 */
export default function ReportGen({ report, tenderId, evaluations = [] }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  const API_BASE = 'http://localhost:8000';

  const handleDownload = async () => {
    setDownloading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/report/${tenderId}`);
      if (!res.ok) throw new Error('Report generation failed');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `CRPF_Tender_Report_${tenderId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  };

  const total = report?.total_bidders || evaluations.length || 0;
  const eligible = report?.eligible_count || evaluations.filter((e) => e.overall_status === 'eligible').length;
  const notEligible = report?.not_eligible_count || evaluations.filter((e) => e.overall_status === 'not_eligible').length;
  const review = report?.manual_review_count || evaluations.filter((e) => e.overall_status === 'manual_review').length;

  return (
    <div>
      {error && (
        <div className="banner banner-error">
          <span>⚠️</span> {error}
          <button className="banner-close" onClick={() => setError('')}>×</button>
        </div>
      )}

      {/* Summary Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value gold">{total}</div>
          <div className="stat-label">Total Bidders</div>
        </div>
        <div className="stat-card">
          <div className="stat-value green">{eligible}</div>
          <div className="stat-label">Eligible</div>
        </div>
        <div className="stat-card">
          <div className="stat-value red">{notEligible}</div>
          <div className="stat-label">Not Eligible</div>
        </div>
        <div className="stat-card">
          <div className="stat-value orange">{review}</div>
          <div className="stat-label">Manual Review</div>
        </div>
      </div>

      {/* Bidder Summary Table */}
      {(report?.bidder_summaries || []).length > 0 && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">📋 Bidder Summary</div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Bidder ID</th>
                <th>Status</th>
                <th>Flagged Items</th>
                <th>Needs Review</th>
              </tr>
            </thead>
            <tbody>
              {report.bidder_summaries.map((b, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{b.bidder_id}</td>
                  <td>
                    <span className={`badge badge-${b.overall_status === 'eligible' ? 'eligible' : b.overall_status === 'not_eligible' ? 'not-eligible' : 'review'}`}>
                      {b.overall_status === 'eligible' ? '✅ Eligible' : b.overall_status === 'not_eligible' ? '❌ Not Eligible' : '⚠️ Review'}
                    </span>
                  </td>
                  <td>{b.flagged_count}</td>
                  <td>{b.human_review_required ? '🔴 Yes' : '🟢 No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Not-eligible reasons */}
      {evaluations.filter((e) => e.overall_status === 'not_eligible').length > 0 && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">❌ Rejection Details</div>
          </div>
          {evaluations.filter((e) => e.overall_status === 'not_eligible').map((ev, i) => (
            <div key={i} style={{ marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                Bidder: {ev.bidder_id}
              </div>
              <div className="rejection-reasons-list">
                <h4>Reasons:</h4>
                <ul>
                  {(ev.rejection_reasons || []).map((r, j) => <li key={j}>{r}</li>)}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Download Button */}
      <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📥</div>
        <div className="card-title" style={{ marginBottom: '8px' }}>Download Full Report</div>
        <div className="card-subtitle" style={{ marginBottom: '24px' }}>
          Generate and download a comprehensive PDF report with full audit trail
        </div>
        <button className="btn btn-primary btn-lg" onClick={handleDownload} disabled={downloading || !tenderId}>
          {downloading ? (
            <><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></span> Generating...</>
          ) : (
            <>📄 Download PDF Report</>
          )}
        </button>
      </div>
    </div>
  );
}
