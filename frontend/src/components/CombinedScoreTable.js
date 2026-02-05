
// frontend/src/components/CombinedScoreTable.js
import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
// Remove saveEditedScores as it won't be used for editing
// import { saveEditedScores, exportTableXLSX } from '../services/api';
import { exportTableXLSX } from '../services/api'; // Only keep exportTableXLSX
import './ScoreContractsMode.css';

const CombinedScoreTable = forwardRef(({ contracts = [], title, loading, setLoading, type, workspaceName }, ref) => {
  // Remove isEditing state
  // const [isEditing, setIsEditing] = useState(false);
  const [displayedContracts, setDisplayedContracts] = useState([]); // Renamed from editedContracts

  useEffect(() => {
    // Just set contracts for display, no deep copy needed if not editing
    setDisplayedContracts(contracts);
  }, [contracts]);

  const rawDataForExport = displayedContracts; // Use displayedContracts for export

  const handleExportXLSX = async () => {
    setLoading(true);
    try {
      const response = await exportTableXLSX(workspaceName, rawDataForExport, title);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.setAttribute('href', url);
      a.setAttribute('download', `${workspaceName}_${title.replace(/\s+/g, "_")}.xlsx`);
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      alert(`${title} exported successfully to XLSX!`);
    } catch (err) {
      console.error(`Error exporting ${title} to XLSX:`, err);
      alert(`Failed to export ${title} to XLSX: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    exportToXLSX: () => {
      handleExportXLSX();
    }
  }));

  return (
    <div className="scoring-matrix-card card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h4 className="card-title">{title}</h4>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleExportXLSX}
            className="button export-btn"
            disabled={loading}
          >
            💾 XLSX
          </button>
        </div>
      </div>
      <div className="scoring-matrix-scroll-wrapper">
        <table className="scoring-matrix-table">
          <thead>
            <tr>
              <th>Vendor</th>
              <th>Technical Score</th>
              <th>Weighted Technical Score</th>
              <th>Financial Score</th>
              <th>Weighted Financial Score</th>
              <th>Combined Score</th>
              <th>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {displayedContracts.map((row, idx) => ( // Use displayedContracts here
              <tr key={row.name || idx}>
                <td>{row.name}</td>
                <td>{row.technical_score ?? '-'}</td> {/* Display directly */}
                <td>{row.weighted_technical_score ?? '-'}</td> {/* Display directly */}
                <td>{row.financial_score ?? '-'}</td> {/* Display directly */}
                <td>{row.weighted_financial_score ?? '-'}</td> {/* Display directly */}
                <td style={{ fontWeight: 'bold' }}>{row.score ?? '-'}</td>
                <td>{row.rationale ?? '-'}</td> {/* Display directly */}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
});

export default CombinedScoreTable;