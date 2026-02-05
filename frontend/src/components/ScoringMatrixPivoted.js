// frontend/src/components/ScoringMatrixPivoted.js
import React, { useState, useEffect, useMemo } from 'react';
import { saveEditedScores, exportTableXLSX } from '../services/api';
import './ScoreContractsMode.css';

const groupByCriterion = (contracts = []) => {
  const grouped = {};
  contracts.forEach(({ Serial, criterion, criteria, name, score, rationale, weight }) => {
    const crit = criterion || criteria;
    if (!crit) return;

    if (!grouped[crit]) {
      grouped[crit] = {
        Serial,
        Weight: weight,
        Vendors: {},
      };
    }
    grouped[crit].Vendors[name] = { score, rationale };
  });
  return grouped;
};

function ScoringMatrixPivoted({ contracts = [], title, loading, setLoading, type, workspaceName, onUpdate }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContracts, setEditedContracts] = useState([]);
  const [forceUpdate, setForceUpdate] = useState(0);

  useEffect(() => {
    console.log(`🟡 [${title}] useEffect triggered: contracts prop =`, contracts);
    // Create a proper deep copy and force update
    const contractsCopy = contracts.map(contract => ({ ...contract }));
    setEditedContracts(contractsCopy);
    setForceUpdate(prev => prev + 1);
    console.log(`🟢 [${title}] editedContracts initialized:`, contractsCopy);
  }, [contracts, title]);

  // Use useMemo to ensure grouping updates when editedContracts changes
  const grouped = useMemo(() => {
    const result = groupByCriterion(editedContracts);
    console.log(`📊 [${title}] Grouped Data (${forceUpdate}):`, result);
    return result;
  }, [editedContracts, title, forceUpdate]);

  const contractNames = useMemo(() => {
    const names = Array.from(new Set(editedContracts.map(c => c.name)));
    console.log(`📛 [${title}] Contract Names:`, names);
    return names;
  }, [editedContracts, title]);

  const tableDisplayDataForExport = Object.entries(grouped).map(([criterion, data]) => {
    const row = {
      Serial: data.Serial ?? '-',
      Criterion: criterion,
      Weight: data.Weight ?? '-',
    };

    contractNames.forEach(name => {
      const score = data.Vendors[name]?.score;
      const weight = data.Weight;

      const weightedCriterionScore =
        typeof score === 'number' && typeof weight === 'number'
          ? (score * weight).toFixed(2)
          : '-';

      row[`${name} Score`] = score ?? '-';
      row[`${name} Weighted Score`] = weightedCriterionScore;
    });

    let combinedRationaleParts = [];
    contractNames.forEach(name => {
      const rationale = data.Vendors[name]?.rationale;
      if (rationale) {
        combinedRationaleParts.push(`${name}: ${rationale}`);
      }
    });
    row.Rationale = combinedRationaleParts.join('\n');

    return row;
  });

  const handleExportXLSX = async () => {
    setLoading(true);
    try {
      console.log(`📤 [${title}] Exporting XLSX:`, tableDisplayDataForExport);
      const response = await exportTableXLSX(workspaceName, tableDisplayDataForExport, title);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.setAttribute('href', url);
      a.setAttribute('download', `${workspaceName}_${title.replace(/\s+/g, "_")}.xlsx`);
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      alert(`${title} exported successfully to XLSX!`);
    } catch (err) {
      console.error(`❌ [${title}] Export failed:`, err);
      alert(`Failed to export ${title} to XLSX: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDataChange = (criterionKey, contractName, field, value) => {
    console.log(`✏️ [${title}] Change: criterion=${criterionKey}, contract=${contractName}, field=${field}, value=${value}`);

    setEditedContracts(prevContracts => {
      // Create a new array with new objects
      const newContracts = prevContracts.map(contract => {
        const matchesCriterion = (contract.criterion === criterionKey || contract.criteria === criterionKey);
        const matchesName = contract.name === contractName;
        
        if (matchesCriterion && matchesName) {
          const updatedContract = { ...contract };
          if (field === 'score') {
            // Handle numeric conversion properly
            updatedContract.score = value === '' ? null : parseFloat(value) || 0;
          } else {
            updatedContract[field] = value;
          }
          console.log(`✅ [${title}] Updated contract:`, updatedContract);
          return updatedContract;
        }
        return contract;
      });

      console.log(`📦 [${title}] Updated editedContracts:`, newContracts);
      
      // Force a re-render by updating the force update counter
      setForceUpdate(prev => prev + 1);
      
      return newContracts;
    });
  };
  
  const handleEditSaveToggle = async () => {
    console.log(`🔁 [${title}] Toggling edit mode: current isEditing=${isEditing}`);
    if (isEditing) {
      setLoading(true);
      try {
        const payload = {};
        if (title === 'Allyin Breakdown') {
          payload.raw_openrouter = { contracts: editedContracts }; // Fixed payload key
        } else if (type === 'openrouter') {
          payload.raw_openrouter = { contracts: editedContracts };
        } else if (type === 'chatgpt') {
          payload.raw_chatgpt = { contracts: editedContracts };
        }        
        console.log(`💾 [${title}] Saving payload:`, payload);
        await saveEditedScores(workspaceName, payload);
        alert(`${title} data saved successfully!`);
        setIsEditing(false);
        
        // Call the callback to trigger final score recalculation
        if (onUpdate) {
          onUpdate();
        }
        
      } catch (err) {
        console.error(`❌ [${title}] Save failed:`, err);
        alert(`Failed to save ${title} data: ${err.response?.data?.detail || err.message}`);
      } finally {
        setLoading(false);
        console.log(`🟢 [${title}] Save complete.`);
      }
    } else {
      setIsEditing(true);
      console.log(`✍️ [${title}] Edit mode activated`);
    }
  };
  return (
    <div className="scoring-matrix-card card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h4 className="card-title">{title}</h4>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={handleEditSaveToggle}
            className={`button edit-save-btn ${isEditing ? 'save-mode' : ''}`}
            disabled={loading}
          >
            {isEditing ? <>💾 Save</> : <>✏️ Edit</>}
          </button>
          {!isEditing && (
            <button
              onClick={handleExportXLSX}
              className="button export-btn"
              disabled={loading}
            >
              💾 XLSX
            </button>
          )}
        </div>
      </div>

      <div className="scoring-matrix-scroll-wrapper">
        <table className="scoring-matrix-table">
          <thead>
            <tr>
              <th>Serial</th>
              <th>Criterion</th>
              <th>Weight</th>
              {contractNames.map(name => <th key={`${name}-score`}>{name} Score</th>)}
              {contractNames.map(name => <th key={`${name}-weighted-score`}>{name} Weighted Score</th>)}
              <th style={{ minWidth: '250px' }}>Rationale</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(grouped).map(([criterion, data]) => (
              <tr key={`${criterion}-${forceUpdate}`}>
                <td>{data.Serial ?? '-'}</td>
                <td>{criterion}</td>
                <td>{data.Weight ?? '-'}</td>
                {contractNames.map(contractName => {
                  const score = data.Vendors[contractName]?.score;
                  return (
                    <td key={`${contractName}-score-data-${forceUpdate}`}>
                      {isEditing ? (
                        <input
                          type="number"
                          value={score === null || score === undefined ? '' : score}
                          onChange={(e) => handleDataChange(criterion, contractName, 'score', e.target.value)}
                          className="input-field"
                          style={{ 
                            width: '60px', 
                            padding: '5px', 
                            borderRadius: '4px', 
                            border: '1px solid #555', 
                            backgroundColor: '#333', 
                            color: '#eee' 
                          }}
                          step="1"
                          min="0"
                        />
                      ) : (
                        score ?? '-'
                      )}
                    </td>
                  );
                })}
                {contractNames.map(contractName => {
                  const score = data.Vendors[contractName]?.score;
                  const weight = data.Weight;
                  const weightedCriterionScore =
                    typeof score === 'number' && typeof weight === 'number'
                      ? (score * weight).toFixed(2)
                      : '-';
                  return <td key={`${contractName}-weighted-score-data-${forceUpdate}`}>{weightedCriterionScore}</td>;
                })}
                <td>
                  {contractNames.map(contractName => {
                    const rationale = data.Vendors[contractName]?.rationale;
                    return rationale ? (
                      <div key={`${contractName}-rationale-${forceUpdate}`} style={{ marginBottom: '5px' }}>
                        <strong>{contractName}:</strong>{' '}
                        {isEditing ? (
                          <textarea
                            value={rationale ?? ''}
                            onChange={(e) => handleDataChange(criterion, contractName, 'rationale', e.target.value)}
                            className="input-field rationale-textarea"
                            rows="2"
                            style={{ 
                              width: '100%', 
                              verticalAlign: 'middle', 
                              padding: '5px', 
                              borderRadius: '4px', 
                              border: '1px solid #555', 
                              backgroundColor: '#333', 
                              color: '#eee' 
                            }}
                          />
                        ) : (
                          rationale ?? '-'
                        )}
                      </div>
                    ) : null;
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ScoringMatrixPivoted;