// frontend/src/components/WorkspaceSelector.js
import React, { useState } from 'react';
// import { FaQuestionCircle, FaStar, FaChartBar} from "react-icons/fa";
function WorkspaceSelector({
  workspaces,
  selectedWorkspace,
  onSelectWorkspace,
  onCreateWorkspace,
  onDeleteWorkspace,
  loading,
}) {
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [showCreateInput, setShowCreateInput] = useState(false);
  const [workspaceToDelete, setWorkspaceToDelete] = useState('');

  const handleSelectChange = (e) => {
    const value = e.target.value;
    if (value === '__create__') {
      setShowCreateInput(true);
      onSelectWorkspace(''); // Clear selected workspace
    } else {
      setShowCreateInput(false);
      onSelectWorkspace(value);
    }
  };

  const handleCreateClick = () => {
    if (newWorkspaceName.trim()) {
      onCreateWorkspace(newWorkspaceName.trim());
      setNewWorkspaceName(''); // Clear after creation
      setShowCreateInput(false); // Hide input after creating
    }
  };

  const handleDeleteClick = () => {
    if (workspaceToDelete) {
      onDeleteWorkspace(workspaceToDelete);
      setWorkspaceToDelete(''); // Clear after deletion
    }
  };

  return (
    <div className="workspace-selector"> {/* Class already exists */}
      <h3 className="card-title">Choose Workspace</h3> {/* Applied card-title */}
      <select
        value={selectedWorkspace || ''}
        onChange={handleSelectChange}
        disabled={loading}
        className="input-field" /* NEW CLASS */
      >
        <option value="">-- Select a workspace --</option>
        {workspaces.map((ws) => (
          <option key={ws} value={ws}>
            {ws}
          </option>
        ))}
        <option value="__create__">Create new...</option>
      </select>

      {showCreateInput && (
        <div style={{ marginTop: '10px' }}>
          <input
            type="text"
            placeholder="Enter new workspace name"
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            disabled={loading}
            className="input-field" /* NEW CLASS */
          />
          <button
            onClick={handleCreateClick}
            disabled={loading || !newWorkspaceName.trim()}
            className="button" /* Applied button class */
          >
            Create Workspace
          </button>
        </div>
      )}

      <div style={{ marginTop: '20px' }}>
        {/* <h3 className="section-title" style={{ color: 'var(--color-danger)' }}>⚠️ Danger Zone: Delete a Workspace</h3> Styled danger zone */}
        <select
          value={workspaceToDelete}
          onChange={(e) => setWorkspaceToDelete(e.target.value)}
          disabled={loading}
          className="input-field" /* NEW CLASS */
        >
          <option value="">Select workspace to delete</option>
          {workspaces.map((ws) => (
            <option key={ws} value={ws}>
              {ws}
            </option>
          ))}
        </select>
        {workspaceToDelete && (
          <p
            className="small-text" /* Applied small-text */
            style={{
              color: 'var(--color-danger)', /* Use design system danger color */
              marginTop: '5px',
            }}
          >
            This will permanently delete all data from '{workspaceToDelete}'. This action cannot be undone.
          </p>
        )}
        <button
          onClick={handleDeleteClick}
          disabled={loading || !workspaceToDelete}
          className="button secondary" /* Applied button secondary class */
        >
          Delete Workspace
        </button>
      </div>
    </div>
  );
}

export default WorkspaceSelector;