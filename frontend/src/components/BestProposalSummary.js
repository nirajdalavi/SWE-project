// frontend/src/components/BestProposalSummary.js
import React, { useState, useEffect } from 'react';
import { saveEditedScores } from '../services/api';
import './ScoreContractsMode.css'; // For general input styles

function BestProposalSummary({ workspaceName, initialSummary, loading, setLoading, uiLanguage = 'en' }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedSummary, setEditedSummary] = useState(null);

  useEffect(() => {
    setEditedSummary(JSON.parse(JSON.stringify(initialSummary)));
  }, [initialSummary]);

  const handleSummaryChange = (field, value, index = null) => {
    setEditedSummary(prev => {
      let newEditedSummary = JSON.parse(JSON.stringify(prev));
      if (!newEditedSummary) {
        newEditedSummary = { best_contract: '', summary: [] };
      }

      if (field === 'best_contract') {
        newEditedSummary.best_contract = value;
      } else if (field === 'summary' && index !== null) {
        if (!newEditedSummary.summary[index]) {
          newEditedSummary.summary[index] = ''; // Initialize if undefined
        }
        newEditedSummary.summary[index] = value;
      }
      return newEditedSummary;
    });
  };

  const addSummaryPoint = () => {
    setEditedSummary(prev => {
      const newEditedSummary = JSON.parse(JSON.stringify(prev));
      if (!newEditedSummary) {
        newEditedSummary = { best_contract: '', summary: [] };
      }
      newEditedSummary.summary.push(''); // Add an empty string for a new point
      return newEditedSummary;
    });
  };

  const removeSummaryPoint = (index) => {
    setEditedSummary(prev => {
      const newEditedSummary = JSON.parse(JSON.stringify(prev));
      if (newEditedSummary && newEditedSummary.summary) {
        newEditedSummary.summary.splice(index, 1);
      }
      return newEditedSummary;
    });
  };

  const handleEditSaveToggle = async () => {
    if (isEditing) {
      // Save logic
      setLoading(true);
      try {
        const payload = {
          summary_of_best: editedSummary
        };
        await saveEditedScores(workspaceName, payload);
        alert("Best proposal summary saved successfully!");
        setIsEditing(false);
      } catch (err) {
        console.error("Error saving best proposal summary:", err);
        alert(`Failed to save best proposal summary: ${err.response?.data?.detail || err.message}`);
      } finally {
        setLoading(false);
      }
    } else {
      // Enter edit mode
      setIsEditing(true);
    }
  };

  if (!editedSummary || (!editedSummary.summary?.length && !isEditing)) {
    return <p>No best proposal summary available.</p>;
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h4 className="card-title">Best Proposal Summary</h4>
        <button
          onClick={handleEditSaveToggle}
          className={`button edit-save-btn ${isEditing ? 'save-mode' : ''}`} // Add save-mode class
          disabled={loading}
        >
          {isEditing ? (
            <>&#x1F4BE; Save</> // Save icon and "Save"
          ) : (
            <>&#x270E; Edit</> // Pencil icon and "Edit"
          )}
        </button>
      </div>
      <p style={{ direction: uiLanguage === 'ar' ? 'rtl' : 'ltr' }}>
        <strong>Best Proposal:</strong>{' '}
        {isEditing ? (
          <input
            type="text"
            value={editedSummary.best_contract ?? ''}
            onChange={(e) => handleSummaryChange('best_contract', e.target.value)}
            className="input-field"
            style={{ 
              width: 'calc(100% - 120px)', 
              padding: '5px', 
              borderRadius: '4px', 
              border: '1px solid #555', 
              backgroundColor: '#333', 
              color: '#eee',
              direction: uiLanguage === 'ar' ? 'rtl' : 'ltr',
              textAlign: uiLanguage === 'ar' ? 'right' : 'left'
            }}
          />
        ) : (
          <span style={{ direction: uiLanguage === 'ar' ? 'rtl' : 'ltr' }}>
            {editedSummary.best_contract ?? '-'}
          </span>
        )}
      </p>
      <ul style={{ direction: uiLanguage === 'ar' ? 'rtl' : 'ltr' }}>
        {(editedSummary.summary || []).map((point, idx) => (
          <li key={idx} style={{ direction: uiLanguage === 'ar' ? 'rtl' : 'ltr' }}>
            {isEditing ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <textarea
                  value={point ?? ''}
                  onChange={(e) => handleSummaryChange('summary', e.target.value, idx)}
                  className="input-field rationale-textarea" // Add specific class for textarea
                  rows="2"
                  style={{ 
                    flexGrow: 1, 
                    padding: '5px', 
                    borderRadius: '4px', 
                    border: '1px solid #555', 
                    backgroundColor: '#333', 
                    color: '#eee',
                    direction: uiLanguage === 'ar' ? 'rtl' : 'ltr',
                    textAlign: uiLanguage === 'ar' ? 'right' : 'left'
                  }}
                />
                <button onClick={() => removeSummaryPoint(idx)} className="button" style={{ background: '#dc3545', color: '#fff', border: 'none', borderRadius: '4px', padding: '5px 10px', cursor: 'pointer' }}>
                  Remove
                </button>
              </div>
            ) : (
              <span style={{ direction: uiLanguage === 'ar' ? 'rtl' : 'ltr' }}>
                {point}
              </span>
            )}
          </li>
        ))}
        {isEditing && (
          <li>
            <button onClick={addSummaryPoint} className="button" style={{ background: '#28a745', color: '#fff', border: 'none', borderRadius: '4px', padding: '5px 10px', cursor: 'pointer' }}>
              Add Point
            </button>
          </li>
        )}
      </ul>
    </div>
  );
}

export default BestProposalSummary;
