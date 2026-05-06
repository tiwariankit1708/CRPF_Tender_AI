import React, { useState } from 'react';

/**
 * FlaggedQueue — Human-in-the-loop review queue.
 */
export default function FlaggedQueue({ audits = [], tenderId, onReviewSubmit }) {
  const [reviewNotes, setReviewNotes] = useState({});
  const [reviewedItems, setReviewedItems] = useState({});
  const [submitting, setSubmitting] = useState({});
  const API_BASE = 'http://localhost:8000';

  const allFlagged = audits.flatMap((audit) =>
    (audit.flagged_items || []).map((item) => ({ ...item, bidder_id: audit.bidder_id }))
  );

  const getConfClass = (c) => c >= 0.75 ? 'confidence-high' : c >= 0.5 ? 'confidence-med' : 'confidence-low';

  const handleReview = async (bidderId, criterionName, action) => {
    const key = `${bidderId}-${criterionName}`;
    setSubmitting((p) => ({ ...p, [key]: true }));
    try {
      const res = await fetch(`${API_BASE}/review/${tenderId}/${bidderId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ criterion_name: criterionName, action, notes: reviewNotes[key] || '' }),
      });
      if (!res.ok) throw new Error('Failed');
      setReviewedItems((p) => ({ ...p, [key]: action }));
      if (onReviewSubmit) onReviewSubmit(bidderId, criterionName, action);
    } catch (e) { console.error(e); }
    finally { setSubmitting((p) => ({ ...p, [key]: false })); }
  };

  if (!allFlagged.length) {
    return (
      <div className="empty-state">
        <div className="empty-icon">✅</div>
        <div className="empty-title">No Flagged Items</div>
        <div className="empty-text">All results passed confidence threshold. No manual review needed.</div>
      </div>
    );
  }

  const grouped = {};
  allFlagged.forEach((item) => {
    if (!grouped[item.bidder_id]) grouped[item.bidder_id] = [];
    grouped[item.bidder_id].push(item);
  });

  return (
    <div>
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div>
            <div className="card-title">🔍 Human Review Queue</div>
            <div className="card-subtitle">{allFlagged.length} item{allFlagged.length !== 1 ? 's' : ''} require attention</div>
          </div>
          <span className="badge badge-review" style={{ fontSize: '0.85rem', padding: '6px 16px' }}>
            {Object.keys(reviewedItems).length} / {allFlagged.length} reviewed
          </span>
        </div>
      </div>

      {Object.entries(grouped).map(([bidderId, items]) => (
        <div key={bidderId} style={{ marginBottom: '32px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
            👤 Bidder: {bidderId} <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400 }}>({items.length} flagged)</span>
          </h3>
          <div className="flagged-list">
            {items.map((item, idx) => {
              const key = `${bidderId}-${item.criterion_name}`;
              const reviewed = reviewedItems[key];
              return (
                <div key={idx} className="flagged-item" style={reviewed ? { opacity: 0.6, borderColor: reviewed === 'approve' ? 'var(--status-eligible)' : 'var(--status-not-eligible)' } : {}}>
                  <div className="flagged-header">
                    <div className="flagged-criterion">{item.criterion_name}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {item.current_verdict && <span className={`badge badge-${item.current_verdict === 'eligible' ? 'eligible' : item.current_verdict === 'not_eligible' ? 'not-eligible' : 'review'}`}>{item.current_verdict.replace('_', ' ')}</span>}
                      <span className={`flagged-confidence ${getConfClass(item.confidence)}`}>{(item.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                  <div className="flagged-note">{item.review_note}</div>
                  {item.evidence_field && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '12px', fontFamily: 'var(--font-mono)' }}>Evidence: <span style={{ color: 'var(--accent-blue-light)' }}>{item.evidence_field}</span></div>}
                  {reviewed ? (
                    <div className={`banner ${reviewed === 'approve' ? 'banner-success' : 'banner-error'}`} style={{ marginBottom: 0 }}>
                      {reviewed === 'approve' ? '✅ Approved' : '❌ Rejected'}{reviewNotes[key] && ` — ${reviewNotes[key]}`}
                    </div>
                  ) : (
                    <div className="flagged-actions">
                      <input type="text" className="review-notes-input" placeholder="Add notes (optional)..." value={reviewNotes[key] || ''} onChange={(e) => setReviewNotes((p) => ({ ...p, [key]: e.target.value }))} />
                      <button className="btn btn-success btn-sm" onClick={() => handleReview(bidderId, item.criterion_name, 'approve')} disabled={submitting[key]}>✅ Approve</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleReview(bidderId, item.criterion_name, 'reject')} disabled={submitting[key]}>❌ Reject</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
