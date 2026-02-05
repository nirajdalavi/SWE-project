// export default FileUpload;

// frontend/src/components/FileUpload.js
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { uploadFiles, getProcessingStatus,
  getGoogleDriveAuthUrl,
  listGoogleDriveFiles,
  uploadFromGoogleDrive,
  getGoogleDriveAuthStatus,
  listGoogleDriveFolders,
  revokeGoogleDriveAccess } from '../services/api';
import { FaGoogleDrive } from 'react-icons/fa';
const POLLING_INTERVAL = 5000;

function FileUpload({ workspaceName, fileType = 'documents', onUploadSuccess }) {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(''); // Use 'message' for all user feedback
  const [error, setError] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const pollingIntervalRef = useRef(null);

  // Ref to track if an upload was just completed and we're waiting for processing to finish
  const justUploadedRef = useRef(false);

  const latestCheckRef = useRef(null); // holds latest checkProcessingStatus

  // Google Drive specific states
  const [googleDriveFiles, setGoogleDriveFiles] = useState([]);
  const [googleDriveFolders, setGoogleDriveFolders] = useState([]);
  const [selectedGdriveFiles, setSelectedGdriveFiles] = useState([]);
  const [currentGdriveFolder, setCurrentGdriveFolder] = useState(null);
  const [showGoogleDriveFilePicker, setShowGoogleDriveFilePicker] = useState(false);
  const [isGdriveAuthenticated, setIsGdriveAuthenticated] = useState(false);
  const [fetchingGoogleDriveFiles, setFetchingGoogleDriveFiles] = useState(false);
  const [googleDriveError, setGoogleDriveError] = useState('');
  const authCallbackProcessedRef = useRef(false);
  const [driveDebug, setDriveDebug] = useState({ filesCount: 0, foldersCount: 0, lastFolder: null });
  const describeFolder = (id) => (id === null ? 'root' : id);
  // const [gdriveFolderStack, setGdriveFolderStack] = useState([]); // for Back navigation

  // Helper: determine if a Drive file is visible in the current folder
  const isFileVisibleInCurrentFolder = useCallback((file) => {
    const parents = Array.isArray(file?.parents) ? file.parents : [];
    // If a file has no parents info, treat it as root-level only
    if (parents.length === 0) {
      return currentGdriveFolder === null;
    }
    // At root: visible if parent includes 'root'
    if (currentGdriveFolder === null) {
      return parents.includes('root');
    }
    // In a folder: visible if that folder id is among parents
    return parents.includes(currentGdriveFolder);
  }, [currentGdriveFolder]);
  // Function to get display name for file types
  const getTypeDisplayName = useCallback((type) => {
    switch (type) {
      case 'documents':
        return 'Contract Documents';
      case 'criteria':
        return 'Evaluation Criteria';
      case 'technical_report':
        return 'Technical Reports';
      case 'financial_report':
        return 'Financial Reports';
      case 'job_description':
        return 'Job Description';
      case 'resumes':
        return 'Resumes';
      default:
        return 'Files';
    }
  }, []); // Memoize this function

  // Dynamically set the card title based on fileType
  const getCardTitle = useCallback(() => {
    return `Upload ${getTypeDisplayName(fileType)}`;
  }, [fileType, getTypeDisplayName]); // Memoize this function

  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
      console.log(`Polling stopped for ${fileType}.`);
    }
  }, [fileType]);

  // startPolling uses a ref to the latest checker to avoid TDZ/circular deps
  const startPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    pollingIntervalRef.current = setInterval(() => {
      if (latestCheckRef.current) {
        latestCheckRef.current();
      }
    }, POLLING_INTERVAL);
  }, []);
  const checkProcessingStatus = useCallback(async () => {
    if (!workspaceName) {
      stopPolling();
      return;
    }

    try {
      const statusRes = await getProcessingStatus(workspaceName);
      const currentlyProcessing = statusRes.data.is_processing;
      const isCriteriaExtracting = statusRes.data.is_criteria_extracting;

      if (!currentlyProcessing && !isCriteriaExtracting) {
        // All processing is complete
        setIsProcessing(false);
        setLoading(false);
        stopPolling();

        // If we just uploaded OR if the message indicated processing, show "Upload completed!"
        if (justUploadedRef.current || message.includes("Processing started") || message.includes("Processing...") || message.includes("extracting criteria") || message.includes("imported and processing started")) {
          setMessage(`${getTypeDisplayName(fileType)} upload and processing completed!`);
          justUploadedRef.current = false; // Reset the ref
          if (onUploadSuccess) {
            onUploadSuccess();
          }
        } else if (!error && !selectedFiles.length) { // Only clear message if no error and no selected files
          // For cases where processing might have finished on backend before frontend checked
          setMessage('');
        }

      } else {
        // Still processing - show appropriate message based on what's happening
        setIsProcessing(true);
        setLoading(true); // Keep button disabled
        
        if (isCriteriaExtracting && fileType === 'job_description') {
          setMessage(`Job description uploaded. Extracting criteria using AI...`);
        } else if (currentlyProcessing) {
          setMessage(`${getTypeDisplayName(fileType)} uploaded. Processing started in the background...`);
        }
        
        if (!pollingIntervalRef.current) { // Only start polling if not already running
          startPolling();
        }
      }
    } catch (err) {
      console.error(`Error checking ${fileType} processing status:`, err);
      setError(`Failed to check ${getTypeDisplayName(fileType)} processing status.`);
      setIsProcessing(false);
      setLoading(false);
      stopPolling();
      setMessage(`Error during ${getTypeDisplayName(fileType)} processing.`);
    }
  }, [workspaceName, onUploadSuccess, stopPolling, message, error, fileType, selectedFiles.length, getTypeDisplayName, startPolling]); // Added getTypeDisplayName to dependencies

  useEffect(() => {
    latestCheckRef.current = checkProcessingStatus;
  }, [checkProcessingStatus]);

  const fetchGoogleDriveFiles = useCallback(async (folderId = null) => {
    if (!workspaceName) return;

    setFetchingGoogleDriveFiles(true);
    setGoogleDriveError('');
    try {
      const compatibleTypes = {
        'resumes': ['pdf', 'doc', 'docx'],
        'job_description': ['pdf', 'doc', 'docx'],
        'documents': ['pdf', 'doc', 'docx']
      };
      const types = compatibleTypes[fileType] || ['pdf', 'doc', 'docx'];

      // const filesResponse = await listGoogleDriveFiles(folderId, types.join(','), workspaceName);
      const filesResponse = await listGoogleDriveFiles(folderId, null, workspaceName);
      const foldersResponse = await listGoogleDriveFolders(workspaceName);

      const files = filesResponse.data.files || [];
      const folders = foldersResponse.data.folders || [];

      setGoogleDriveFiles(files);
      setGoogleDriveFolders(folders);
      setDriveDebug({ filesCount: files.length, foldersCount: folders.length, lastFolder: folderId || null });
      console.log('[GDRIVE] fetched', { folderId, files, folders });

      if (files.length === 0 && folders.length === 0) {
        setMessage("No relevant files or folders found in your Google Drive.");
      }
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setGoogleDriveError('Google Drive connection expired or invalid. Please reconnect.');
        setIsGdriveAuthenticated(false);
      } else {
        setGoogleDriveError(`Failed to load Google Drive files: ${err.response?.data?.detail || err.message}`);
      }
    } finally {
      setFetchingGoogleDriveFiles(false);
    }
  }, [workspaceName, fileType]);



  const handleOpenGoogleDrivePicker = async () => {
    setGoogleDriveError('');
    setShowGoogleDriveFilePicker(true);
    setFetchingGoogleDriveFiles(true);

    try {
      const statusResponse = await getGoogleDriveAuthStatus(workspaceName);
      const isAuthenticated = statusResponse.data.authenticated;

      setIsGdriveAuthenticated(isAuthenticated);
      console.log('[GDRIVE] status', { isAuthenticated });

      if (isAuthenticated) {
        fetchGoogleDriveFiles();
      } else {
        const authResponse = await getGoogleDriveAuthUrl(workspaceName);
        const authUrl = authResponse.data.auth_url;
        // Open in a centered popup
        const w = 520, h = 640;
        const y = window.top.outerHeight / 2 + window.top.screenY - (h / 2);
        const x = window.top.outerWidth / 2 + window.top.screenX - (w / 2);
        const popup = window.open(authUrl, 'gdrive_auth', `width=${w},height=${h},left=${x},top=${y}`);

        const onMsg = (e) => {
          try {
            const allowedOrigins = [
              window.location.origin,
              (process.env.REACT_APP_BACKEND_ORIGIN || (process.env.REACT_APP_BACKEND_HOST === 'localhost' ? 'http://localhost:8000' : `https://${process.env.REACT_APP_BACKEND_HOST}`))
            ];
            if (!allowedOrigins.includes(e.origin)) return;
            const data = e.data || {};
            if (data.type === 'gdrive-auth' && data.workspace === workspaceName) {
              window.removeEventListener('message', onMsg);
              if (popup && !popup.closed) popup.close();
              if (data.status === 'success') {
                setIsGdriveAuthenticated(true);
                setShowGoogleDriveFilePicker(true);
                fetchGoogleDriveFiles();
              } else {
                setIsGdriveAuthenticated(false);
                setGoogleDriveError('Google Drive authentication failed. Please try again.');
              }
            }
          } catch (_) {}
        };
        window.addEventListener('message', onMsg);
      }
    } catch (err) {
      setGoogleDriveError(err.response?.data?.detail || 'Failed to connect to Google Drive.');
      setFetchingGoogleDriveFiles(false);
    }
  };

  const handleInitiateGoogleDriveAuth = async () => {
    setGoogleDriveError('');
    try {
      const authResponse = await getGoogleDriveAuthUrl(workspaceName);
      const authUrl = authResponse.data.auth_url;
      const w = 520, h = 640;
      const y = window.top.outerHeight / 2 + window.top.screenY - (h / 2);
      const x = window.top.outerWidth / 2 + window.top.screenX - (w / 2);
      const popup = window.open(authUrl, 'gdrive_auth', `width=${w},height=${h},left=${x},top=${y}`);

      const onMsg = (e) => {
        try {
          const allowedOrigins = [
            window.location.origin,
            (process.env.REACT_APP_BACKEND_ORIGIN || (process.env.REACT_APP_BACKEND_HOST === 'localhost' ? 'http://localhost:8000' : `https://${process.env.REACT_APP_BACKEND_HOST}`))
          ];
          if (!allowedOrigins.includes(e.origin)) return;
          const data = e.data || {};
          if (data.type === 'gdrive-auth' && data.workspace === workspaceName) {
            window.removeEventListener('message', onMsg);
            if (popup && !popup.closed) popup.close();
            if (data.status === 'success') {
              setIsGdriveAuthenticated(true);
              setShowGoogleDriveFilePicker(true);
              fetchGoogleDriveFiles();
            } else {
              setIsGdriveAuthenticated(false);
              setGoogleDriveError('Google Drive authentication failed. Please try again.');
            }
          }
        } catch (_) {}
      };
      window.addEventListener('message', onMsg);
    } catch (err) {
      setGoogleDriveError('Failed to initiate Google Drive connection. Please check backend logs and credentials.json.');
    }
  };

  const handleGdriveFileSelection = (fileId) => {
    setSelectedGdriveFiles(prev => {
      const isSelected = prev.includes(fileId);
      return isSelected ? prev.filter(f => f !== fileId) : [...prev, fileId];
    });
  };

  
  const handleSelectAllVisibleFiles = () => {
    const visibleIds = googleDriveFiles
      .filter(isFileVisibleInCurrentFolder)
      .map(f => f.id);
    setSelectedGdriveFiles(prev => Array.from(new Set([...prev, ...visibleIds])));
  };
  
  const handleClearSelectedFiles = () => {
    setSelectedGdriveFiles([]);
  };

  const handleImportFromGoogleDrive = async () => {
    if (selectedGdriveFiles.length === 0) {
      setGoogleDriveError('Please select at least one file to import.');
      return;
    }
  
    setLoading(true);
    setMessage('');
    setError('');
    setIsProcessing(true);
    justUploadedRef.current = true;
    setGoogleDriveError('');

    try {
      stopPolling();
      // const res = await uploadFromGoogleDrive(workspaceName, selectedGdriveFiles, fileType);
      // const res = await uploadFromGoogleDrive(workspaceName, selectedGdriveFiles, fileType);
      const ids = Array.isArray(selectedGdriveFiles)
        ? [...new Set(selectedGdriveFiles.filter(Boolean))]
        : (selectedGdriveFiles ? [selectedGdriveFiles] : []);

      if (ids.length === 0) {
        throw new Error('No Google Drive files selected.');
      }

      const res = await uploadFromGoogleDrive(workspaceName, ids, fileType);

      setMessage(res.data.message || `File(s) imported and processing started.`);

      startPolling();
      checkProcessingStatus();

      setShowGoogleDriveFilePicker(false);
      setSelectedGdriveFiles([]);
      
      // Call onUploadSuccess immediately for Google Drive uploads
      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || `Failed to import file(s) from Google Drive.`;
      setError(errorMessage);
      setLoading(false);
      setIsProcessing(false);
      stopPolling();
      setMessage(`Import failed.`);
      justUploadedRef.current = false;
      if (err.response && err.response.status === 401) {
        setGoogleDriveError('Google Drive connection expired. Please reconnect.');
        setIsGdriveAuthenticated(false);
      } else {
        setGoogleDriveError(errorMessage);
      }
    }
  };

  const handleGdriveFolderSelect = (folderId) => {
    setCurrentGdriveFolder(folderId);
    fetchGoogleDriveFiles(folderId);
  };

  
  // const handleGdriveFolderSelect = (folderId) => {
  //       setGdriveFolderStack(prev => [...prev, currentGdriveFolder]); // push current (null at root)
  //       setCurrentGdriveFolder(folderId);
  //       fetchGoogleDriveFiles(folderId);
  //     };

  const handleGoBack = () => {
    const parentFolderId = googleDriveFolders.find(f => f.id === currentGdriveFolder)?.parents?.[0] || null;
    setCurrentGdriveFolder(parentFolderId);
    fetchGoogleDriveFiles(parentFolderId);
  };
  // const handleGoBack = () => {
  //       setGdriveFolderStack(prev => {
  //         if (prev.length === 0) {
  //           setCurrentGdriveFolder(null);
  //           fetchGoogleDriveFiles(null);
  //           return [];
  //   +      }
  //   +      const next = [...prev];
  //   +      const parentId = next.pop() || null;
  //   +      setCurrentGdriveFolder(parentId);
  //   +      fetchGoogleDriveFiles(parentId);
  //   +      return next;
  //   +    });
  //   +  };

  const handleGoogleDriveRevoke = async () => {
    try {
      await revokeGoogleDriveAccess(workspaceName);
      setIsGdriveAuthenticated(false);
      setGoogleDriveFiles([]);
      setGoogleDriveFolders([]);
      setSelectedGdriveFiles([]);
      setMessage('Google Drive access revoked successfully');
      setGoogleDriveError('');
    } catch (error) {
      setGoogleDriveError('Error revoking Google Drive access: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Handler to allow user to explicitly switch Google account (force re-auth)
  const handleSwitchGoogleAccount = async () => {
    try {
      try {
        await revokeGoogleDriveAccess(workspaceName);
      } catch (err) {
        console.warn('[GDRIVE] revoke failed, proceeding to re-auth anyway:', err?.response?.data || err?.message || err);
      }
      // Clear local auth/UI state either way
      setIsGdriveAuthenticated(false);
      setGoogleDriveFiles([]);
      setGoogleDriveFolders([]);
      setSelectedGdriveFiles([]);
      setGoogleDriveError('');
      // Immediately initiate a fresh OAuth flow so the Google account chooser appears
      const authResponse = await getGoogleDriveAuthUrl(workspaceName);
      window.location.href = authResponse.data.auth_url;
    } catch (err) {
      setGoogleDriveError('Could not initiate Google re-auth: ' + (err.response?.data?.detail || err.message));
    }
  };




  // Primary useEffect for component lifecycle
  useEffect(() => {
    // Initial status check when the component mounts or workspace/fileType changes
    // This will check if there's ongoing processing from a previous session
    const urlParams = new URLSearchParams(window.location.search);
    const authStatus = urlParams.get('google_drive_auth');
    const workspaceFromUrl = urlParams.get('workspace');

    if (authStatus === 'success' && workspaceFromUrl === workspaceName && !authCallbackProcessedRef.current) {
      authCallbackProcessedRef.current = true;
      setMessage('Google Drive connected successfully!');
      setIsGdriveAuthenticated(true);
      setShowGoogleDriveFilePicker(true);
      fetchGoogleDriveFiles();
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    checkProcessingStatus();

    // Cleanup function: stop polling when component unmounts
    return () => {
      stopPolling();
      // Reset component-specific refs when unmounting
      justUploadedRef.current = false;
    };
  }, [workspaceName, fileType, checkProcessingStatus, stopPolling, fetchGoogleDriveFiles]); // fileType as a dependency to re-run effect for each component instance

  useEffect(() => {
    // This effect ensures polling starts if checkProcessingStatus reports active
    // and polling wasn't already running
    if (isProcessing && !pollingIntervalRef.current) {
      startPolling();
    }
  }, [isProcessing, startPolling]);

  const handleFileChange = (event) => {
    setSelectedFiles(Array.from(event.target.files));
    setError(''); // Clear errors on new file selection
    setMessage(''); // Clear messages on new file selection
    justUploadedRef.current = false; // Reset upload flag on new file selection
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (selectedFiles.length === 0) {
      setError('Please select files to upload.');
      return;
    }

    setLoading(true);
    setMessage(''); // Clear previous messages before starting new upload
    setError('');
    setIsProcessing(true); // Optimistically set to processing
    justUploadedRef.current = true; // Set flag that an upload just started

    try {
      stopPolling(); // Stop any ongoing polling before starting a new upload

      const res = await uploadFiles(workspaceName, selectedFiles, fileType);
      console.log(`✅ Uploaded ${fileType}:`, res.data.message);
      // Set initial upload message (which includes "Processing started")
      setMessage(res.data.message || `${getTypeDisplayName(fileType)} uploaded. Processing started in the background.`);
      setSelectedFiles([]); // Clear selected files in UI

      startPolling(); // Start polling for background task completion
      checkProcessingStatus(); // Immediate check after initiating upload
      
      // Call onUploadSuccess immediately for local uploads
      if (onUploadSuccess) {
        onUploadSuccess();
      }

    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        `Failed to upload ${getTypeDisplayName(fileType)}.`
      );
      setLoading(false);
      setIsProcessing(false); // Clear processing state on immediate upload failure
      stopPolling(); // Ensure polling stops if upload itself fails
      setMessage(`Upload failed for ${getTypeDisplayName(fileType)}.`); // Clear any processing message with an error
      justUploadedRef.current = false; // Reset upload flag on failure
    }
  };

  return (
    <div className="file-upload-selection">
      <h3 className="card-title">
        {getCardTitle()} {/* Use the dynamic title here */}
      </h3>
      <form onSubmit={handleUpload}>
        <div className="upload-box">
          <span className="upload-icon">📄</span>
          <p className="small-text">Drag and drop files here</p>
          <input
            type="file"
            multiple
            onChange={handleFileChange}
            disabled={loading || isProcessing}
            style={{ display: 'none' }}
            id={`file-upload-input-${fileType}`}
          />
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
            <label htmlFor={`file-upload-input-${fileType}`} className="button secondary">Browse local files</label>
            <button
              type="button"
              className="button secondary"
              onClick={handleOpenGoogleDrivePicker}
              disabled={loading || isProcessing}
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <FaGoogleDrive /> Browse Google Drive
            </button>
          </div>
        </div>
        {selectedFiles.length > 0 && (
          <div className="upload-files-list">
            {selectedFiles.map((file, index) => (
              <span key={file.name + index} className="file-chip">
                {file.name}
                <span onClick={() => setSelectedFiles(selectedFiles.filter((_, i) => i !== index))} className="remove">x</span>
              </span>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button type="submit" disabled={loading || isProcessing || selectedFiles.length === 0} className="button">
            {loading && !isProcessing ? 'Uploading...' : isProcessing ? 'Processing...' : 'Upload Files'}
          </button>
        </div>
      </form>

      {/* Message display for consistency */}
      {message && <p className="small-text" style={{ color: 'var(--color-accent)', marginTop: '1em' }}>{message}</p>}
      {isProcessing && !error && <p className="small-text" style={{ color: 'var(--color-primary)', marginTop: '1em' }}>Processing in background. Please wait...</p>}
      {error && <p className="error-message" style={{ marginTop: '1em' }}>Error: {error}</p>}
      {googleDriveError && <p className="error-message" style={{ marginTop: '1em' }}>Google Drive Error: {googleDriveError}</p>}

{showGoogleDriveFilePicker && (
  <div className="google-drive-picker-overlay">
    <div className="google-drive-picker-content">
      {fetchingGoogleDriveFiles ? (
        <>
          <h3>Select from Google Drive</h3>
          <p>Loading files from Google Drive...</p>
        </>
      ) : isGdriveAuthenticated ? (
        <>
          <h3>Select from Google Drive</h3>
          {/* Sticky Action Buttons at Top */}
          <div className="sticky-actions">
            <button type="button" className="button secondary" onClick={handleClearSelectedFiles}>
              Clear
            </button>
            <button
              type="button"
              className="button"
              onClick={handleImportFromGoogleDrive}
              disabled={selectedGdriveFiles.length === 0 || loading || isProcessing}
            >
              Import ({selectedGdriveFiles.length})
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => setShowGoogleDriveFilePicker(false)}
            >
              Close
            </button>
          </div>
          
          {/* File Content Area */}
          <div className="file-content">
            {currentGdriveFolder && (
              <div className="folder-nav">
                <button onClick={handleGoBack}>← Back</button>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '6px 0 10px' }}>
              <small>Folder: <strong>{describeFolder(currentGdriveFolder)}</strong> • Files: {driveDebug.filesCount} • Folders: {driveDebug.foldersCount}</small>
            </div>
            <ul className="google-drive-files-list">
              {googleDriveFolders
                .filter(folder => {
                  if (currentGdriveFolder === null) {
                    // show root-level (no parents or includes 'root')
                    return !folder.parents || folder.parents.length === 0 || folder.parents.includes('root');
                  }
                  return Array.isArray(folder.parents) && folder.parents.includes(currentGdriveFolder);
                })
                .map((folder) => (
                  <li key={folder.id} className="folder-item" onClick={() => handleGdriveFolderSelect(folder.id)}>
                    <span>📁 {folder.name}</span>
                  </li>
                ))}
              {(() => {
                const visibleFiles = googleDriveFiles.filter(file => {
                  // If no parents info, treat as root-level
                  if (!Array.isArray(file.parents) || file.parents.length === 0) {
                    return currentGdriveFolder === null;
                  }
                  return currentGdriveFolder === null
                    ? file.parents.includes('root')
                    : file.parents.includes(currentGdriveFolder);
                });
                const filesToShow = visibleFiles.length > 0 ? visibleFiles : googleDriveFiles;
                return filesToShow.length > 0 ? (
                  filesToShow.map((file) => (
                    <li
                      key={file.id}
                      className={selectedGdriveFiles.includes(file.id) ? 'selected file-item' : 'file-item'}
                    >
                      <input
                        type="checkbox"
                        checked={selectedGdriveFiles.includes(file.id)}
                        onChange={() => handleGdriveFileSelection(file.id)}
                        style={{ marginRight: '8px' }}
                      />
                      <button
                        type="button"
                        onClick={() => handleGdriveFileSelection(file.id)}
                        style={{ background: 'none', border: 'none', padding: 0, margin: 0, cursor: 'pointer', font: 'inherit' }}
                      >
                        {file.name}
                      </button>
                    </li>
                  ))
                ) : (
                  <p>No files found or supported files in this folder. Supported types: PDF, DOCX, or DOC.</p>
                );
              })()}
            </ul>
          </div>
        </>
      ) : (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <p>{googleDriveError || 'Google Drive is not connected or requires re-authentication.'}</p>
          <button className="button" onClick={handleInitiateGoogleDriveAuth}>Connect Google Drive</button>
          <button type="button" className="button secondary" style={{ marginLeft: '10px' }} onClick={() => setShowGoogleDriveFilePicker(false)}>Close</button>
        </div>
      )}
    </div>
  </div>
)}
    </div>
  );
}

export default FileUpload;
