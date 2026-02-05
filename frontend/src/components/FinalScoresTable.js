// frontend/src/components/FinalScoresTable.js
import React, { useState, useEffect } from 'react';
// Remove saveEditedScores as it won't be used for editing
// import { saveEditedScores } from '../services/api';
import './ScoreContractsMode.css';

function FinalScoresTable({ workspaceName, initialOpenrouterScores, initialChatgptScores, compareResponsesEnabled, loading, setLoading }) {
  // Remove isEditing state
  // const [isEditing, setIsEditing] = useState(false);
  const [displayedOpenrouterScores, setDisplayedOpenrouterScores] = useState({}); // Renamed for clarity
  const [displayedChatgptScores, setDisplayedChatgptScores] = useState({}); // Renamed for clarity

  useEffect(() => {
    // No deep copy needed if not editing
    console.log('[FinalScoresTable] Props received:', { initialOpenrouterScores, initialChatgptScores });
    setDisplayedOpenrouterScores(initialOpenrouterScores || {});
    setDisplayedChatgptScores(initialChatgptScores || {});
  }, [initialOpenrouterScores, initialChatgptScores]);

  // Remove handleFinalScoreChange as editing is gone
  // const handleFinalScoreChange = (source, contractName, field, value) => { ... };

  // Remove handleEditSaveToggle as editing is gone
  // const handleEditSaveToggle = async () => { ... };

  const contracts = new Set([
    ...Object.keys(displayedOpenrouterScores || {}),
    ...Object.keys(displayedChatgptScores || {})
  ]);

  // This check might need adjustment if you want to explicitly show "No scores" even if editing
  // But if editing is removed, this simplifies.
  if (!contracts.size) {
    return <p>No final scores available to display.</p>;
  }

  const getScoreKey = (scores) => {
    if (!scores || Object.keys(scores).length === 0) return '';
    const sample = Object.values(scores)[0];
    console.log('[FinalScoresTable] getScoreKey sample:', sample);
    if (sample?.score_out_of_100 !== undefined) return 'score_out_of_100';
    if (sample?.score_out_of_50 !== undefined) return 'score_out_of_50';
    return '';
  };

  const openrouterScoreKey = getScoreKey(displayedOpenrouterScores);
  const chatgptScoreKey = getScoreKey(displayedChatgptScores);
  
  console.log('[FinalScoresTable] Displayed scores:', {
    displayedOpenrouterScores,
    displayedChatgptScores,
    openrouterScoreKey,
    chatgptScoreKey,
    contracts: [...contracts]
  });

  return (
    <div className="score-summary-table card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h4 className="card-title">Final Scores Summary</h4>
        {/* REMOVE THE EDIT/SAVE BUTTON */}
        {/* <button
          onClick={handleEditSaveToggle}
          className={`button edit-save-btn ${isEditing ? 'save-mode' : ''}`}
          disabled={loading}
        >
          {isEditing ? (
            <>&#x1F4BE; Save</>
          ) : (
            <>&#x270E; Edit</>
          )}
        </button> */}
      </div>
      <div className="scoring-matrix-scroll-wrapper">
        <table className="scoring-matrix-table">
          <thead>
            <tr>
              <th>Contract</th>
              <th>Allyin Score {openrouterScoreKey === 'score_out_of_100' ? '(out of 100)' : '(out of 50)'}</th>
              <th>Allyin %</th>
              {compareResponsesEnabled && (
                <>
                  <th>ChatGPT Score {chatgptScoreKey === 'score_out_of_100' ? '(out of 100)' : '(out of 50)'}</th>
                  <th>ChatGPT %</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {[...contracts].map(contract => (
              <tr key={contract}>
                <td>{contract}</td>
                <td>{displayedOpenrouterScores[contract]?.[openrouterScoreKey] ?? '-'}</td> 
                <td>{displayedOpenrouterScores[contract]?.percentage ?? '-'}</td> 
                {compareResponsesEnabled && (
                  <>
                    <td>{displayedChatgptScores[contract]?.[chatgptScoreKey] ?? '-'}</td> 
                    <td>{displayedChatgptScores[contract]?.percentage ?? '-'}</td> 
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default FinalScoresTable;