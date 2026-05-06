import React from 'react';

/**
 * AuditView — Criterion-by-criterion breakdown with evidence highlighting.
 * Shows detailed evaluation results for a selected bidder.
 */
export default function AuditView({ evaluation, bidderData }) {
  if (!evaluation) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📊</div>
        <div className="empty-title">No Evaluation Selected</div>
        <div className="empty-text">
          Select a bidder from the Results tab to view their detailed evaluation.
        </div>
      </div>
    );
  }

  const { bidder_id, overall_status, criteria_results = [], rejection_reasons = [] } = evaluation;

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case 'eligible':
        return <span className="badge badge-eligible">✅ Eligible</span>;
      case 'not_eligible':
        return <span className="badge badge-not-eligible">❌ Not Eligible</span>;
      case 'manual_review':
        return <span className="badge badge-review">⚠️ Manual Review</span>;
      default:
        return <span className="badge">{verdict}</span>;
    }
  };

  const getOverallBadge = (status) => {
    switch (status) {
      case 'eligible':
        return <span className="badge badge-eligible" style={{ fontSize: '0.85rem', padding: '6px 16px' }}>✅ ELIGIBLE</span>;
      case 'not_eligible':
        return <span className="badge badge-not-eligible" style={{ fontSize: '0.85rem', padding: '6px 16px' }}>❌ NOT ELIGIBLE</span>;
      case 'manual_review':
        return <span className="badge badge-review" style={{ fontSize: '0.85rem', padding: '6px 16px' }}>⚠️ MANUAL REVIEW</span>;
      default:
        return null;
    }
  };

  // Group criteria by type
  const grouped = {};
  criteria_results.forEach((cr) => {
    const type = cr.criterion_type || 'other';
    if (!grouped[type]) grouped[type] = [];
    grouped[type].push(cr);
  });

  const typeLabels = {
    technical: '🔧 Technical Criteria',
    financial: '💰 Financial Criteria',
    compliance: '📜 Compliance Criteria',
    other: '📋 Other Criteria',
  };

  return (
    <div className="audit-view">
      {/* Bidder Summary Header */}
      <div className="card" style={{ marginBottom: '20px' }}>
        <div className="card-header">
          <div>
            <div className="card-title">Bidder: {bidder_id}</div>
            <div className="card-subtitle">
              {criteria_results.length} criteria evaluated
            </div>
          </div>
          {getOverallBadge(overall_status)}
        </div>

        {/* Rejection Reasons — prominently displayed */}
        {rejection_reasons.length > 0 && (
          <div className="rejection-reasons-list">
            <h4>❌ Reasons for Not Eligible:</h4>
            <ul>
              {rejection_reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Summary Stats */}
        <div className="stats-grid" style={{ marginTop: '16px', marginBottom: '0' }}>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div className="stat-value green" style={{ fontSize: '1.5rem' }}>
              {criteria_results.filter((c) => c.verdict === 'eligible').length}
            </div>
            <div className="stat-label">Eligible</div>
          </div>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div className="stat-value red" style={{ fontSize: '1.5rem' }}>
              {criteria_results.filter((c) => c.verdict === 'not_eligible').length}
            </div>
            <div className="stat-label">Not Eligible</div>
          </div>
          <div className="stat-card" style={{ padding: '12px' }}>
            <div className="stat-value orange" style={{ fontSize: '1.5rem' }}>
              {criteria_results.filter((c) => c.verdict === 'manual_review').length}
            </div>
            <div className="stat-label">Review</div>
          </div>
        </div>
      </div>

      {/* Criteria Breakdown by Type */}
      {Object.entries(grouped).map(([type, criteria]) => (
        <div key={type} style={{ marginBottom: '24px' }}>
          <h3 style={{
            fontSize: '1rem',
            fontWeight: 600,
            color: 'var(--text-primary)',
            marginBottom: '12px',
            paddingBottom: '8px',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            {typeLabels[type] || type}
          </h3>

          <div className="audit-criteria-list">
            {criteria.map((cr, idx) => (
              <div key={idx} className="audit-criterion">
                <div>
                  <div className="audit-criterion-name">{cr.criterion_name}</div>
                  <div className="audit-criterion-type">
                    {cr.is_mandatory ? '🔴 Mandatory' : '🟡 Optional'}
                    {cr.threshold && ` • Threshold: ${cr.threshold}`}
                  </div>
                  <div className="audit-reason">
                    <strong>Reason:</strong> {cr.reason}
                  </div>
                  {cr.extracted_value && (
                    <div className="audit-evidence">
                      Extracted Value: <span>{cr.extracted_value}</span>
                    </div>
                  )}
                  {cr.evidence_field && (
                    <div className="audit-evidence">
                      Source Field: <span>{cr.evidence_field}</span>
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right' }}>
                  {getVerdictBadge(cr.verdict)}
                  {cr.confidence !== undefined && (
                    <div style={{
                      marginTop: '8px',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      color: cr.confidence >= 0.75
                        ? 'var(--status-eligible)'
                        : cr.confidence >= 0.5
                          ? 'var(--status-review)'
                          : 'var(--status-not-eligible)',
                    }}>
                      {(cr.confidence * 100).toFixed(0)}% confidence
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Bidder Raw Data */}
      {bidderData && (
        <div className="card" style={{ marginTop: '24px' }}>
          <div className="card-header">
            <div className="card-title">📄 Extracted Bidder Data</div>
          </div>
          <table className="data-table">
            <tbody>
              <tr>
                <td style={{ fontWeight: 600, width: '200px' }}>Annual Turnover</td>
                <td>{bidderData.annual_turnover || '—'}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {bidderData.confidence_scores?.annual_turnover
                    ? `${(bidderData.confidence_scores.annual_turnover * 100).toFixed(0)}%`
                    : '—'}
                </td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Projects Completed</td>
                <td>{bidderData.projects_completed ?? '—'}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {bidderData.confidence_scores?.projects_completed
                    ? `${(bidderData.confidence_scores.projects_completed * 100).toFixed(0)}%`
                    : '—'}
                </td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Certifications</td>
                <td>
                  {bidderData.certifications?.length > 0
                    ? bidderData.certifications.join(', ')
                    : '—'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {bidderData.confidence_scores?.certifications
                    ? `${(bidderData.confidence_scores.certifications * 100).toFixed(0)}%`
                    : '—'}
                </td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Registration Number</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {bidderData.registration_number || '—'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {bidderData.confidence_scores?.registration_number
                    ? `${(bidderData.confidence_scores.registration_number * 100).toFixed(0)}%`
                    : '—'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
