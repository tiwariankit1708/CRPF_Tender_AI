import React, { useRef, useState } from 'react';

/**
 * UploadZone — Drag-and-drop file upload component with PDF validation.
 * Supports both tender and bid document uploads.
 */
export default function UploadZone({
  type = 'tender', // 'tender' or 'bid'
  tenderId = '',
  onUploadComplete,
  disabled = false,
}) {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState(null);
  const [bidderIdInput, setBidderIdInput] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileInputRef = useRef(null);

  const isTender = type === 'tender';
  const API_BASE = 'http://localhost:8000';

  const validateFile = (f) => {
    if (!f) return 'No file selected';
    if (!f.name.toLowerCase().endsWith('.pdf')) return 'Only PDF files are accepted';
    if (f.size > 50 * 1024 * 1024) return 'File size must be under 50MB';
    return null;
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    if (disabled) return;

    const droppedFile = e.dataTransfer.files[0];
    const err = validateFile(droppedFile);
    if (err) {
      setError(err);
      return;
    }
    setFile(droppedFile);
    setError('');
    setSuccess('');
  };

  const handleFileSelect = (e) => {
    const selected = e.target.files[0];
    const err = validateFile(selected);
    if (err) {
      setError(err);
      return;
    }
    setFile(selected);
    setError('');
    setSuccess('');
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!isTender && !bidderIdInput.trim()) {
      setError('Please enter a Bidder ID');
      return;
    }
    if (!isTender && !tenderId) {
      setError('Please upload a tender document first');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      let url;
      if (isTender) {
        url = `${API_BASE}/upload/tender`;
      } else {
        url = `${API_BASE}/upload/bid`;
        formData.append('bidder_id', bidderIdInput.trim());
        formData.append('tender_id', tenderId);
      }

      const res = await fetch(url, { method: 'POST', body: formData });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed (${res.status})`);
      }

      const data = await res.json();
      setSuccess(
        isTender
          ? `Tender uploaded! ID: ${data.tender_id}`
          : `Bid uploaded for bidder: ${data.bidder_id}`
      );
      setFile(null);
      setBidderIdInput('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      if (onUploadComplete) onUploadComplete(data);
    } catch (e) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-card">
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

      <div
        className={`upload-zone ${dragOver ? 'drag-over' : ''} ${disabled ? 'disabled' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && fileInputRef.current?.click()}
      >
        <div className="upload-icon">{isTender ? '📋' : '📄'}</div>
        <div className="upload-title">
          {isTender ? 'Upload Tender Document' : 'Upload Bidder Document'}
        </div>
        <div className="upload-subtitle">
          Drag & drop a PDF here, or click to browse
        </div>
        <button className="upload-btn" disabled={disabled}>
          📎 Choose PDF File
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />

        {file && (
          <div className="upload-file-info">
            📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)
          </div>
        )}
      </div>

      {!isTender && (
        <div className="bidder-input-group">
          <input
            type="text"
            className="bidder-input"
            placeholder="Enter Bidder ID (e.g., BIDDER-001)"
            value={bidderIdInput}
            onChange={(e) => setBidderIdInput(e.target.value)}
            disabled={disabled}
          />
        </div>
      )}

      {file && (
        <div style={{ marginTop: '16px', textAlign: 'center' }}>
          <button
            className="btn btn-primary btn-lg"
            onClick={handleUpload}
            disabled={uploading || disabled}
          >
            {uploading ? (
              <>
                <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></span>
                Processing...
              </>
            ) : (
              <>🚀 Upload & Analyze</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
