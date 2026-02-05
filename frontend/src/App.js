// frontend/src/App.js
import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import WorkspaceSelector from './components/WorkspaceSelector';
import AskQuestionMode from './components/AskQuestionMode';
import ScoreContractsMode from './components/ScoreContractsMode';
import CombinedEvaluationMode from './components/CombinedEvaluationMode';
import ResumeScoringMode from './components/ResumeScoringMode';
import FeatureRequestMode from './components/FeatureRequestMode';
import VendorRecommendationMode from './components/VendorRecommendationMode';
import VendorComparisonMode from './components/VendorComparisonMode';
import VendorResearchMode from './components/VendorResearchMode';
import AuditMode from './components/AuditMode';
import LegalMode from './components/LegalMode';
import PromptManager from './components/PromptManager';
import FileUpload from './components/FileUpload'; // Keep this import, still used by Ask Mode
import MetricsChart from './components/MetricsChart';
import ContactForm from './components/ContactForm';
import { getWorkspaces, createWorkspace, deleteWorkspace, getPrompts } from './services/api';
import { FaQuestionCircle, FaStar, FaChartBar, FaFilePdf, FaBuilding, FaPlus, FaEnvelope, FaGavel, FaSearch, FaTable } from 'react-icons/fa';
import ThemeToggle from './components/ThemeToggle';

function App() {
    const [hasAccess, setHasAccess] = useState(null);
    const [workspaces, setWorkspaces] = useState([]);
    const [selectedWorkspace, setSelectedWorkspace] = useState('');
    const [mode, setMode] = useState('ask');
    const [prompts, setPrompts] = useState([]);
    const [appLoading, setAppLoading] = useState(false);
    const [workspaceOperationLoading, setWorkspaceOperationLoading] = useState(false);
    const [error, setError] = useState('');
    const [selectedPrompt, setSelectedPrompt] = useState('');
    const [showSidePanel, setShowSidePanel] = useState(false);
    const [compareResponsesEnabled, setCompareResponsesEnabled] = useState(false);
    const [shareDataWithChatgpt, setShareDataWithChatgpt] = useState(false);
    const [useWebSearch, setUseWebSearch] = useState(false);
    const [specificUrl, setSpecificUrl] = useState('');
    const [responseSize, setResponseSize] = useState('medium');
    const [responseType, setResponseType] = useState('sentence');
    const initialProgressSteps = [ // Define outside to avoid recreation on re-renders
      { label: "Understanding the question...", status: "Waiting" },
      { label: "Finding relevant documents...", status: "Waiting" },
      { label: "Generating response...", status: "Waiting" }
    ];
    const [progressSteps, setProgressSteps] = useState(initialProgressSteps); // Initialize with initialAllSteps
    const [currentStepIndex, setCurrentStepIndex] = useState(0);
    const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost'; // Fallback to local if not set
    // useEffect(() => {
    //     fetch(`http://${backendHost}:8000`)
    //         .then(res => {
    //             if (res.status === 403) {
    //                 setHasAccess(false);
    //             } else {
    //                 setHasAccess(true);
    //             }
    //         })
    //         .catch(() => setHasAccess(false));
    // }, [backendHost]);

    // Always set access to true - licensing disabled
    useEffect(() => {
        setHasAccess(true);
    }, []);

    const fetchWorkspaces = useCallback(async () => {
        try {
            setWorkspaceOperationLoading(true);
            const response = await getWorkspaces();
            setWorkspaces(response.data.workspaces);
        } catch (err) {
            setError('Failed to fetch workspaces.');
            console.error('Error fetching workspaces:', err);
        } finally {
            setWorkspaceOperationLoading(false);
        }
    }, []);

    const [darkMode, setDarkMode] = useState(false); // Default to light mode
    const [isContactFormOpen, setIsContactFormOpen] = useState(false);

    useEffect(() => {
      document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    }, [darkMode]);
    

    const fetchPrompts = useCallback(async (workspace) => {
        try {
            setWorkspaceOperationLoading(true);
            const response = await getPrompts(workspace);
            setPrompts(response.data || []);
        } catch (err) {
            setError('Failed to fetch prompts.');
            console.error('Error fetching prompts:', err);
            setPrompts([]);
        } finally {
            setWorkspaceOperationLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchWorkspaces();
    }, [fetchWorkspaces]);

    useEffect(() => {
        if (selectedWorkspace) {
            fetchPrompts(selectedWorkspace);
            setSelectedPrompt('');
            console.log(`[App.js] Workspace changed to: ${selectedWorkspace}, selectedPrompt reset to empty.`);
        } else {
            setPrompts([]);
            setSelectedPrompt('');
            console.log(`[App.js] No workspace selected, selectedPrompt reset to empty.`);
        }
    }, [selectedWorkspace, fetchPrompts]);

    useEffect(() => {
        setSelectedPrompt('');
        console.log(`[App.js] Mode changed to: ${mode}, selectedPrompt reset to empty.`);
    }, [mode]);


    const handleCreateWorkspace = async (name) => {
        if (workspaceOperationLoading || appLoading) return;
        try {
            setWorkspaceOperationLoading(true);
            await createWorkspace(name);
            await fetchWorkspaces();
            alert(`Workspace '${name}' created!`);
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to create workspace.');
            console.error('Error creating workspace:', err);
        } finally {
            setWorkspaceOperationLoading(false);
        }
    };

    const handleDeleteWorkspace = async (name) => {
        if (workspaceOperationLoading || appLoading) return;
        if (window.confirm(`Are you sure you want to delete workspace "${name}"? This action is irreversible and will delete all data.`)) {
            try {
                setWorkspaceOperationLoading(true);
                await deleteWorkspace(name);
                alert(`Workspace '${name}' deleted.`);
                await fetchWorkspaces();
                setSelectedWorkspace('');
            } catch (err) {
                setError(err.response?.data?.detail || 'Failed to delete workspace.');
                console.error('Error deleting workspace:', err);
            } finally {
                setWorkspaceOperationLoading(false);
            }
        }
    };

    const handleSelectPromptFromManager = (prompt) => {
        setSelectedPrompt(prompt);
        console.log(`[App.js] Prompt selected: ${prompt}`);
    };

    // if (hasAccess === false) {
    //     return (
    //         <div className="App" style={{ textAlign: "center", marginTop: "100px", fontFamily: "sans-serif", backgroundColor: "#f5f5f5", height: "100vh" }}>
    //             <div
    //                 style={{
    //                     maxWidth: "400px",
    //                     margin: "auto",
    //                     background: "#fff",
    //                     borderRadius: "20px",
    //                     padding: "0rem",
    //                     boxShadow: "0 4px 20px rgba(0, 0, 0, 0.1)"
    //                 }}
    //             >
    //                 <div style={{ backgroundColor: "#2b3a55", padding: "1rem", borderTopLeftRadius: "20px", borderTopRightRadius: "20px", color: "#fff" }}>
    //                     <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🔒</div>
    //                     <h2 style={{ margin: 0 }}>Trial Expired</h2>
    //                     <p style={{ margin: "0.5rem 0 0" }}>Enter your license to continue</p>
    //                 </div>
    //                 <div style={{ backgroundColor: "#fff", padding: "1.5rem", borderBottomLeftRadius: "20px", borderBottomRightRadius: "20px" }}>
    //                     <div style={{ backgroundColor: "#fff8db", border: "1px solid #ffe58f", padding: "1rem", borderRadius: "8px", marginBottom: "1rem", textAlign: "left" }}>
    //                         <strong style={{ color: "#d48806" }}>⚠️ Your trial period has ended</strong>
    //                         <p style={{ margin: "0.5rem 0 0", color: "#8c8c8c" }}>Please enter your license key to continue using the application</p>
    //                     </div>
    //                     <form
    //                         style={{ display: "flex", flexDirection: "column", alignItems: "center" }}
    //                         onSubmit={async (e) => {
    //                             e.preventDefault();
    //                             const licenseKey = e.target.license.value;
    //                             const res = await fetch(`http://${backendHost}:8000/enter_license`, {
    //                                 method: "POST",
    //                                 headers: { "Content-Type": "application/x-www-form-urlencoded" },
    //                                 body: new URLSearchParams({ license_key: licenseKey }),
    //                             });
    //                             if (res.ok) {
    //                                 window.location.reload();
    //                             } else {
    //                                 alert("License activation failed.");
    //                             }
    //                         }}
    //                     >
    //                         <label htmlFor="license" style={{ display: "block", textAlign: "left", marginBottom: "0.5rem", fontWeight: "bold", color: "black" }}>License Key</label>
    //                         <input
    //                             id="license"
    //                             name="license"
    //                             placeholder="🔑 Enter your license key here..."
    //                             required
    //                             style={{ padding: "12px", width: "320px", borderRadius: "8px", border: "1px solid #ccc", marginBottom: "1rem" }}
    //                         />
    //                         <button
    //                             type="submit"
    //                             style={{
    //                                 padding: "12px",
    //                                 width: "350px",
    //                                 backgroundColor: "#2b78e4",
    //                                 color: "#fff",
    //                                 border: "none",
    //                                 borderRadius: "8px",
    //                                 fontWeight: "bold",
    //                                 cursor: "pointer"
    //                             }}
    //                         >
    //                             Activate License ➜
    //                         </button>
    //                     </form>
    //                 </div>
    //             </div>
    //         </div>
    //     );
    // }

    // if (hasAccess === null) return <p>Loading license check...</p>;

    return (
        <div className="App">
          <div className="theme-toggle-button">
            <button onClick={() => setDarkMode(prev => !prev)}>
              {darkMode ? '☀️' : '🌙'}
            </button>
          </div>
    
          <div className="main-container">
            <aside className="sidebar">
              <div className="sidebar-logo">
                <img src="/logo.png" className="sidebar-logo-img" alt="ProcuraAI Logo" />
                <div className="sidebar-logo-text-container">
                  <span className="sidebar-logo-text">ContractIQ</span>
                  <small className="powered-by-text">By Procura</small>
                </div>
              </div>
    
              {workspaceOperationLoading && <p className="small-text">Loading...</p>}
              {error && <p className="error-message">{error}</p>}
    
              <div className="workspace-selector card">
                <h3 className="section-title">Workspace</h3>
                <WorkspaceSelector
                  workspaces={workspaces}
                  selectedWorkspace={selectedWorkspace}
                  onSelectWorkspace={setSelectedWorkspace}
                  onCreateWorkspace={handleCreateWorkspace}
                  onDeleteWorkspace={handleDeleteWorkspace}
                  loading={workspaceOperationLoading}
                />
              </div>
    
              <div className="mode-selector-vertical">
                <button onClick={() => setMode('ask')} className={mode === 'ask' ? 'active' : ''}>
                  <FaQuestionCircle className="icon" /> Ask a Question
                </button>
                
                <hr style={{ margin: '1rem 0', border: 'none', borderTop: '1px solid var(--color-border)' }} />
                <h4 style={{ margin: '0.5rem 1rem', fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--color-text)' }}>PROCUREMENT</h4>

                <button onClick={() => setMode('vendor')} className={mode === 'vendor' ? 'active' : ''}>
                  <FaBuilding className="icon" /> Vendor Recommendations
                </button>
                
                {/* Show Alternate Vendors Toggle - Only show when in vendor mode */}
                {mode === 'vendor' && (
                  <div className="left-panel-toggle">
                    <div className="left-panel-toggle-content">
                      <span className="left-panel-toggle-label">
                        Sponsored Vendors
                      </span>
                      <label className="toggle-switch" style={{ margin: 0 }}>
                        <input
                          type="checkbox"
                          checked={showSidePanel}
                          onChange={(e) => setShowSidePanel(e.target.checked)}
                          disabled={appLoading}
                        />
                        <span className="toggle-slider round"></span>
                      </label>
                    </div>
                  </div>
                )}
                
                <button onClick={() => setMode('vendor-comparison')} className={mode === 'vendor-comparison' ? 'active' : ''}>
                  <FaTable className="icon" /> Vendor Comparison
                </button>
                
                <button onClick={() => setMode('vendor-research')} className={mode === 'vendor-research' ? 'active' : ''}>
                  <FaSearch className="icon" /> Vendor Research
                </button>
                <hr style={{ margin: '1rem 0', border: 'none', borderTop: '1px solid var(--color-border)' }} />
                
                <h4 style={{ margin: '0.5rem 1rem', fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--color-text)' }}>RFPs & RFQs</h4>

                <button onClick={() => setMode('score')} className={mode === 'score' ? 'active' : ''}>
                  <FaStar className="icon" /> Score Contracts
                </button>
                <button onClick={() => setMode('combined')} className={mode === 'combined' ? 'active' : ''}>
                  <FaChartBar className="icon" /> Combined Evaluation
                </button>
                <button onClick={() => setMode('audit')} className={mode === 'audit' ? 'active' : ''}>
                  <FaChartBar className="icon" /> Contract Audit
                </button>
                <button onClick={() => setMode('legal')} className={mode === 'legal' ? 'active' : ''}>
                  <FaGavel className="icon" /> Legal Analysis
                </button>
                
                <hr style={{ margin: '1rem 0', border: 'none', borderTop: '1px solid var(--color-border)' }} />
                
                <h4 style={{ margin: '0.5rem 1rem', fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--color-text)' }}>HR</h4>
                
                <button onClick={() => setMode('resume')} className={mode === 'resume' ? 'active' : ''}>
                  <FaFilePdf className="icon" /> Resume Scoring
                </button>
                
                <hr style={{ margin: '1rem 0', border: 'none', borderTop: '1px solid var(--color-border)' }} />
                
                <h4 style={{ margin: '0.5rem 1rem', fontSize: '0.9rem', fontWeight: 'bold', color: 'var(--color-text)' }}>FEEDBACK</h4>
                
                <button onClick={() => setMode('feature-request')} className={mode === 'feature-request' ? 'active' : ''}>
                  <FaPlus className="icon" /> Request Feature
                </button>
              </div>
    
                            {selectedWorkspace && mode !== 'resume' && mode !== 'vendor' && mode !== 'vendor-comparison' && mode !== 'vendor-research' && mode !== 'audit' && mode !== 'legal' && (
                <div className="prompt-manager card">
                  <h3 className="section-title">Quick Prompts</h3>
                  <div className="quick-prompts-list">
                    {prompts.map((prompt, index) => {
                      const cleanedPrompt = prompt.replace(/^Prompt\s*\d+:\s*/, '');
                      return (
                        <button
                          key={index}
                          className={`quick-prompt-button ${selectedPrompt === prompt ? 'active' : ''}`}
                          onClick={() => handleSelectPromptFromManager(cleanedPrompt)}
                        >
                          {cleanedPrompt}
                        </button>
                      );
                    })}
                    {/* {selectedPrompt && (
                      <button className="use-prompt-button-full" onClick={() => setMode('ask')}>
                        ✓ Use This Prompt
                      </button>
                    )} */}
                  </div>
                </div>
              )}

              {mode !== 'resume' && mode !== 'vendor' && mode !== 'vendor-comparison' && mode !== 'vendor-research' && mode !== 'audit' && (
                <div className="card">
                  <h3 className="section-title">Response Settings</h3>
                <div style={{ padding: '0.5rem 0', display: 'flex', alignItems: 'center' }}>
                  <label className="toggle-switch" style={{ marginRight: '10px' }}>
                    <input
                      type="checkbox"
                      checked={compareResponsesEnabled}
                      onChange={(e) => {
                          setCompareResponsesEnabled(e.target.checked);
                          // If comparison is disabled, also disable sharing data
                          if (!e.target.checked) {
                              setShareDataWithChatgpt(false);
                          }
                      }}
                      disabled={appLoading}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <span className="small-text">ChatGPT Comparison</span>
                </div>

                {/* NEW TOGGLE: Share data with ChatGPT */}
                <div style={{ padding: '0.5rem 0', display: 'flex', alignItems: 'center' }}>
                  <label className="toggle-switch" style={{ marginRight: '10px' }}>
                    <input
                      type="checkbox"
                      id="shareDataWithChatgpt"
                      checked={shareDataWithChatgpt}
                      // Disable if compareResponsesEnabled is false or if app is loading
                      disabled={!compareResponsesEnabled || appLoading}
                      onChange={(e) => setShareDataWithChatgpt(e.target.checked)}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <span className="small-text">Share Data with ChatGPT</span>
                </div>

                {/* NEW TOGGLE: Web Search */}
                <div style={{ padding: '0.5rem 0', display: 'flex', alignItems: 'center' }}>
                  <label className="toggle-switch" style={{ marginRight: '10px' }}>
                    <input
                      type="checkbox"
                      id="useWebSearch"
                      checked={useWebSearch}
                      disabled={appLoading}
                      onChange={(e) => setUseWebSearch(e.target.checked)}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <span className="small-text">Web Search</span>
                </div>

                {/* URL Input for specific website */}
                {useWebSearch && (
                  <div style={{ padding: '0.5rem 0' }}>
                    <label htmlFor="specificUrl" className="small-text" style={{ display: 'block', marginBottom: '0.5rem' }}>
                      Specific Website URL (optional):
                    </label>
                    <input
                      type="url"
                      id="specificUrl"
                      value={specificUrl}
                      onChange={(e) => setSpecificUrl(e.target.value)}
                      placeholder="https://example.com"
                      disabled={appLoading}
                      style={{
                        width: '100%',
                        padding: '0.5rem',
                        border: '1px solid var(--color-border)',
                        borderRadius: '4px',
                        fontSize: '0.9rem',
                        backgroundColor: 'var(--color-background)',
                        color: 'var(--color-text)'
                      }}
                    />
                    <small style={{ color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>
                      Leave empty for general web search, or enter a specific URL to scrape that website
                    </small>
                  </div>
                )}
    
                {mode === 'ask' && (
                  <>
                    <div style={{ padding: '0.5rem 0' }}>
                      <label htmlFor="response-size-select" className="small-text">Response Length:</label>
                      <select
                        id="response-size-select"
                        value={responseSize}
                        onChange={(e) => setResponseSize(e.target.value)}
                        disabled={appLoading}
                        className="input-field"
                      >
                        <option value="short">Short (1–2 sentences)</option>
                        <option value="medium">Medium (3–4 sentences)</option>
                        <option value="long">Long (Detailed)</option>
                      </select>
                    </div>
    
                    <div style={{ padding: '0.5rem 0' }}>
                      <label htmlFor="response-type-select" className="small-text">Format:</label>
                      <select
                        id="response-type-select"
                        value={responseType}
                        onChange={(e) => setResponseType(e.target.value)}
                        disabled={appLoading}
                        className="input-field"
                      >
                        <option value="sentence">Structured with sentences</option>
                        <option value="points">Structured with bullets</option>
                      </select>
                    </div>
                  </>
                )}
              </div>
              )}
    
              {selectedWorkspace && (
                <div className="metrics-chart-card card">
                  <MetricsChart workspaceName={selectedWorkspace} />
                </div>
              )}
              
              {/* Contact Us Button - Bottom of Sidebar */}
              <div className="contact-us-section">
                <button 
                  className="contact-us-button"
                  onClick={() => {
                    console.log('Contact us button clicked!');
                    console.log('Current isContactFormOpen:', isContactFormOpen);
                    setIsContactFormOpen(true);
                    console.log('After setting isContactFormOpen to true');
                  }}
                >
                  <FaEnvelope className="icon" />
                  Contact Us
                </button>
               
              </div>
            </aside>
    
            <main className="main-content">
            <h2 className="card-title" style={{ marginBottom: '2rem' }}>Workspace Overview</h2>

            {/* Feature Request Mode - Available without workspace selection */}
            {mode === 'feature-request' && (
                <FeatureRequestMode
                    key={`feature-request-${mode}`}
                />
            )}

            {selectedWorkspace ? (
                <>
                <div className="interaction-block">
                    {/* Ask Mode */}
                    {mode === 'ask' && (
                    <AskQuestionMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        initialQuestion={selectedPrompt}
                        compareResponsesEnabled={compareResponsesEnabled}
                        shareDataWithChatgpt={shareDataWithChatgpt}
                        useWebSearch={useWebSearch}
                        specificUrl={specificUrl}
                        responseSize={responseSize}
                        responseType={responseType}
                        mode={mode}
                        setLoading={setAppLoading}
                        loading={appLoading}
                        progressSteps={progressSteps}
                        setProgressSteps={setProgressSteps}
                        currentStepIndex={currentStepIndex}
                        setCurrentStepIndex={setCurrentStepIndex}
                    />
                    )}

                    {/* Vendor Recommendation Mode */}
                    {mode === 'vendor' && (
                    <VendorRecommendationMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                        showSidePanel={showSidePanel}
                        setShowSidePanel={setShowSidePanel}
                    />
                    )}

                    {/* Vendor Comparison Mode */}
                    {mode === 'vendor-comparison' && (
                    <VendorComparisonMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                    />
                    )}

                    {/* Vendor Research Mode */}
                    {mode === 'vendor-research' && (
                    <VendorResearchMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                        showSidePanel={showSidePanel}
                        setShowSidePanel={setShowSidePanel}
                    />
                    )}

                    {/* Score Mode */}
                    {mode === 'score' && (
                    <ScoreContractsMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        initialCriterion={selectedPrompt}
                        compareResponsesEnabled={compareResponsesEnabled}
                        shareDataWithChatgpt={shareDataWithChatgpt} 
                        mode={mode}
                        setLoading={setAppLoading}
                        loading={appLoading}
                        progressSteps={progressSteps}
                        setProgressSteps={setProgressSteps}
                        currentStepIndex={currentStepIndex}
                        setCurrentStepIndex={setCurrentStepIndex}
                    />
                    )}

                    {/* Combined Mode */}
                    {mode === 'combined' && (
                    <CombinedEvaluationMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        mode={mode}
                        setLoading={setAppLoading}
                        loading={appLoading}
                        progressSteps={initialProgressSteps} // Pass initial steps for combined
                        setProgressSteps={setProgressSteps}
                        currentStepIndex={currentStepIndex}
                        setCurrentStepIndex={setCurrentStepIndex}
                    />
                    )}

                    {/* Audit Mode */}
                    {mode === 'audit' && (
                    <AuditMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                    />
                    )}

                    {/* Legal Analysis Mode */}
                    {mode === 'legal' && (
                    <LegalMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                    />
                    )}

                    {/* Resume Scoring Mode */}
                    {mode === 'resume' && (
                    <ResumeScoringMode
                        key={`${selectedWorkspace}-${mode}`}
                        workspaceName={selectedWorkspace}
                        setLoading={setAppLoading}
                        loading={appLoading}
                    />
                    )}



                    {/* AI is thinking — only for Ask mode */}
                    {appLoading && progressSteps.length > 0 && mode === 'ask' && (
                    <div
                      className="loading-progress-box"
                      style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        flexDirection: 'column',
                        padding: '2rem',
                        textAlign: 'center',
                        width: '100%',
                      }}
                    >
                      <h3>AI is thinking...</h3>
                      <video
                        src="/ai-thinking.mp4"
                        className="loading-icon"
                        autoPlay
                        loop
                        muted
                        playsInline
                        style={{ maxWidth: '350px', marginTop: '1rem' }}
                      />
                      <p style={{ marginTop: '1rem', color: '#666' }}>
                        Please wait while the AI processes your request.<br />
                        This may take a moment.
                      </p>
                    </div>
                    )}


                    {/* File Upload: Ask Mode */}
                    {mode === 'ask' && (
                    <div className="file-upload-card card">
                        <FileUpload
                        key="upload-contract"
                        workspaceName={selectedWorkspace}
                        fileType="contract"
                        onUploadSuccess={fetchWorkspaces}
                        />
                    </div>
                    )}

                    {/*
                       REMOVED File Uploads for Combined Mode from App.js.
                       These are now handled directly within CombinedEvaluationMode.js.
                    */}
                </div>
                </>
            ) : (
                <div className="welcome-page" style={{ display: (selectedWorkspace && ['ask', 'vendor', 'vendor-comparison', 'vendor-research', 'score', 'combined', 'resume', 'audit'].includes(mode)) || mode === 'feature-request' ? 'none' : 'block' }}>
                    <div className="welcome-header">
                        <h1 className="welcome-title">What would you like to do today?</h1>
                        <p className="welcome-subtitle">Choose your workflow to get started</p>
                    </div>
                    
                    <div className="workflow-grid">
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M21 21L16.514 16.506L21 21ZM19 10.5C19 15.194 15.194 19 10.5 19C5.806 19 2 15.194 2 10.5C2 5.806 5.806 2 10.5 2C15.194 2 19 5.806 19 10.5Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Find Vendors</h3>
                            <p className="workflow-description">Get AI-powered vendor recommendations based on your project requirements and budget</p>
                            <button className="workflow-button" onClick={() => setMode('vendor')}>
                                Start Vendor Search
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M14 2V8H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M16 13H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M16 17H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M10 9H9H8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Evaluate Contracts</h3>
                            <p className="workflow-description">Upload RFP responses and contracts to get automated scoring and recommendations</p>
                            <button className="workflow-button" onClick={() => setMode('score')}>
                                Score Documents
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M3 3V21H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M9 9L12 6L16 10L21 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M21 5H16V10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Combined Evaluation</h3>
                            <p className="workflow-description">Comprehensive analysis combining multiple evaluation criteria for thorough assessment</p>
                            <button className="workflow-button" onClick={() => setMode('combined')}>
                                Start Evaluation
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M9 12L11 14L15 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Contract Audit</h3>
                            <p className="workflow-description">Comprehensive audit of all contracts with detailed risk assessment and compliance review</p>
                            <button className="workflow-button" onClick={() => setMode('audit')}>
                                Start Audit
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Screen Resumes</h3>
                            <p className="workflow-description">Upload job descriptions and resumes to get AI-powered candidate rankings</p>
                            <button className="workflow-button" onClick={() => setMode('resume')}>
                                Evaluate Candidates
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M9.09 9C9.3251 8.33167 9.78918 7.76811 10.4 7.40913C11.0108 7.05016 11.7289 6.91894 12.4272 7.03871C13.1255 7.15849 13.7588 7.52152 14.2151 8.06353C14.6713 8.60553 14.9211 9.30197 14.92 10C14.92 12 11.92 13 11.92 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    <path d="M12 17H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Ask Questions</h3>
                            <p className="workflow-description">Ask questions about contracts, vendors, or processes to get instant AI-powered insights</p>
                            <button className="workflow-button" onClick={() => setMode('ask')}>
                                Start Asking
                            </button>
                        </div>
                        
                        <div className="workflow-card">
                            <div className="workflow-icon">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                            </div>
                            <h3 className="workflow-title">Request Feature</h3>
                            <p className="workflow-description">Suggest new features or improvements to help us make ContractIQ even better</p>
                            <button className="workflow-button" onClick={() => setMode('feature-request')}>
                                Submit Request
                            </button>
                        </div>
                    </div>
                    
                    <div className="welcome-footer">
                        <h3 className="footer-title">New to ContractIQ?</h3>
                        <p className="footer-description">Start with vendor recommendations - it's the fastest way to see AI-powered procurement in action</p>
                    </div>
                </div>
            )}
            </main>




          </div>
          
          {/* Contact Form Modal */}
          <ContactForm 
            isOpen={isContactFormOpen}
            onClose={() => setIsContactFormOpen(false)}
          />
        </div>
      );
    }
    
    export default App;