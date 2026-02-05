// frontend/src/components/PromptManager.js
import React from 'react';

function PromptManager({ prompts, setMode, selectedWorkspace, onSelectPrompt }) {
  const promptsToDisplay = prompts; // Prompts are now a simple array

  const handlePromptClick = (prompt) => {
    if (selectedWorkspace) {
      onSelectPrompt(prompt);
    }
  };

  return (
    <div className="prompt-manager"> {/* Class already exists */}
      <h3 className="section-title">Suggested Prompts</h3> {/* Applied section-title */}
      {promptsToDisplay && promptsToDisplay.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}> {/* Container for chips */}
          {promptsToDisplay.map((prompt, index) => (
            <button
              key={index}
              onClick={() => handlePromptClick(prompt)}
              className="prompt-chip" /* NEW CLASS */
            >
              {prompt}
            </button>
          ))}
        </div>
      ) : (
        <p className="small-text">No prompts available for this workspace. Upload contracts to generate some!</p> 
      )}
    </div>
  );
}

export default PromptManager;

