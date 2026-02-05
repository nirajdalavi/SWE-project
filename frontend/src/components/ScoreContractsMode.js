// frontend/src/components/ScoreContractsMode.js
import React, { useState, useEffect } from 'react';
import { scoreContracts, compareResponses, submitAdmin, exportReport, translateText, getContractScores, getJobStatus } from '../services/api'; // Import exportReport and translateText
import './ScoreContractsMode.css';
import ScoringMatrixPivoted from './ScoringMatrixPivoted';
import FinalScoresTable from './FinalScoresTable'; // Import new component
import BestProposalSummary from './BestProposalSummary'; // Import new component
import FileUpload from './FileUpload';

import { getBackendBaseUrl } from '../utils/apiUtils';

const BACKEND_URL = getBackendBaseUrl();

// ADD 'loading' to the destructured props
function ScoreContractsMode({ workspaceName, initialCriterion, compareResponsesEnabled, shareDataWithChatgpt, mode, setLoading, loading, progressSteps, currentStepIndex, setProgressSteps, setCurrentStepIndex, }) { // NEW PROP: shareDataWithChatgpt
  const isInitialMount = React.useRef(true);

  const [criterion, setCriterion] = useState(initialCriterion || '');
  const [maxScore, setMaxScore] = useState(5);
  const [scoreResults, setScoreResults] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [comparison, setComparison] = useState(null);
  const [adminComment, setAdminComment] = useState('');
  
  // NEW STATE: Add state for dynamic final scores
  const [finalOpenrouterScores, setFinalOpenrouterScores] = useState({});
  const [finalChatgptScores, setFinalChatgptScores] = useState({});
  
  // Translation states
  const [uiLanguage, setUiLanguage] = useState('en');
  const [translationCache, setTranslationCache] = useState({});
  const [translatedComparison, setTranslatedComparison] = useState(null);
  const [translatedScoreResults, setTranslatedScoreResults] = useState(null);
  const [isTranslating, setIsTranslating] = useState(false);
  
  // Async job states (async mode always enabled)
  const [jobId, setJobId] = useState(null);

  // Polling function for job status
  const pollJobStatus = async (jobId, maxAttempts = 600, pollInterval = 3000) => {
    let attempts = 0;
    
    const poll = async () => {
      try {
        attempts++;
        const response = await getJobStatus(jobId);
        const job = response.data;
        
        // No UI progress updates needed - just silent polling
        
        // Check if job is complete
        if (job.status === 'SUCCESS') {
          setScoreResults(job.result);
          setFinalOpenrouterScores(job.result.final_scores_openrouter || {});
          setFinalChatgptScores(job.result.final_scores_chatgpt || {});
          setJobId(null);
          setSuccess('Contracts scored successfully! Results are now saved and available.');
          
          // Handle comparison if enabled
          if (compareResponsesEnabled) {
            const openrouterResultString = JSON.stringify(job.result.final_scores_openrouter, null, 2);
            const chatgptResultString = JSON.stringify(job.result.final_scores_chatgpt, null, 2);
            
            if (openrouterResultString && chatgptResultString) {
              try {
                const compRes = await compareResponses(openrouterResultString, chatgptResultString);
                setComparison(compRes.data);
              } catch (compErr) {
                console.error('Error comparing scoring results:', compErr);
              }
            }
          }
          
          setLoading(false);
          return;
        } else if (job.status === 'FAILURE') {
          setError(job.error || 'Job failed');
          setJobId(null);
          setLoading(false);
          return;
        } else if (job.status === 'NOT_FOUND') {
          setError('Job not found');
          setJobId(null);
          setLoading(false);
          return;
        }
        
        // Continue polling if job is still in progress
        if (attempts < maxAttempts) {
          setTimeout(poll, pollInterval);
        } else {
          setError('Job polling timeout');
          setJobId(null);
          setLoading(false);
        }
      } catch (error) {
        setError(`Error checking job status: ${error.message}`);
        setJobId(null);
        setLoading(false);
      }
    };
    
    // Start polling
    poll();
  };


  // Function to fetch saved contract scores
  const fetchSavedContractScores = async () => {
    try {
      const response = await getContractScores(workspaceName);
      setScoreResults(response.data);
      console.log('Loaded saved contract scores:', response.data);
    } catch (err) {
      if (err.response?.status === 404) {
        console.log('No saved contract scores found - this is normal for new workspaces');
      } else {
        console.error('Error fetching saved contract scores:', err);
      }
    }
  };

  // Load saved contract scores when component mounts
  useEffect(() => {
    if (workspaceName) {
      fetchSavedContractScores();
    }
  }, [workspaceName]);

  // Translation function with caching
  const translateTextWithCache = async (text, targetLang) => {
    if (!text || targetLang === 'en') return text;
    
    const cacheKey = `${text}_${targetLang}`;
    if (translationCache[cacheKey]) {
      return translationCache[cacheKey];
    }
    
    try {
      console.log('Translating text to', targetLang);
      const response = await translateText(text, targetLang);
      const translated = response.data.translated_text;
      
      // Only cache if translation is different from original (indicates success)
      if (translated && translated !== text) {
        setTranslationCache(prev => ({ ...prev, [cacheKey]: translated }));
        return translated;
      } else {
        console.warn('Translation returned same text, using original');
        return text;
      }
    } catch (error) {
      console.error('Translation failed:', error);
      // Don't cache failed translations
      return text; // Return original text if translation fails
    }
  };

  // Function to translate scoreResults
  const translateScoreResults = async (results) => {
    if (!results || uiLanguage === 'en') return results;

    try {
      const translatedResults = { ...results };

      // Translate summary_of_best if it exists
      if (results.summary_of_best) {
        const summaryObj = results.summary_of_best;
        translatedResults.summary_of_best = {
          ...summaryObj,
          best_contract: summaryObj.best_contract ? await translateTextWithCache(summaryObj.best_contract, 'ar') : summaryObj.best_contract,
          summary: summaryObj.summary ? await Promise.all(
            summaryObj.summary.map(async (point) => 
              typeof point === 'string' ? await translateTextWithCache(point, 'ar') : point
            )
          ) : summaryObj.summary
        };
      }

      // Translate contract details in raw_openrouter
      if (results.raw_openrouter?.contracts) {
        translatedResults.raw_openrouter = {
          ...results.raw_openrouter,
          contracts: await Promise.all(
            results.raw_openrouter.contracts.map(async (contract) => ({
              ...contract,
              content: contract.content ? await translateTextWithCache(contract.content, 'ar') : contract.content,
              reason: contract.reason ? await translateTextWithCache(contract.reason, 'ar') : contract.reason,
              rationale: contract.rationale ? await translateTextWithCache(contract.rationale, 'ar') : contract.rationale,
              criterion: contract.criterion ? await translateTextWithCache(contract.criterion, 'ar') : contract.criterion,
              criteria: contract.criteria ? await translateTextWithCache(contract.criteria, 'ar') : contract.criteria
            }))
          )
        };
      }

      // Translate contract details in raw_chatgpt
      if (results.raw_chatgpt?.contracts) {
        translatedResults.raw_chatgpt = {
          ...results.raw_chatgpt,
          contracts: await Promise.all(
            results.raw_chatgpt.contracts.map(async (contract) => ({
              ...contract,
              content: contract.content ? await translateTextWithCache(contract.content, 'ar') : contract.content,
              reason: contract.reason ? await translateTextWithCache(contract.reason, 'ar') : contract.reason,
              rationale: contract.rationale ? await translateTextWithCache(contract.rationale, 'ar') : contract.rationale,
              criterion: contract.criterion ? await translateTextWithCache(contract.criterion, 'ar') : contract.criterion,
              criteria: contract.criteria ? await translateTextWithCache(contract.criteria, 'ar') : contract.criteria
            }))
          )
        };
      }

      return translatedResults;
    } catch (error) {
      console.error('Error translating scoreResults:', error);
      return results;
    }
  };

  // Handle translation when language changes
  useEffect(() => {
    const handleTranslation = async () => {
      if (uiLanguage === 'ar') {
        // Check if we already have translations
        if (translatedComparison && translatedScoreResults) {
          console.log('Using existing Arabic translations');
          setIsTranslating(false);
          return;
        }

        setIsTranslating(true);
        try {
          // Translate comparison if it exists and not already translated
          if (comparison && !translatedComparison) {
            console.log('Translating comparison to Arabic...');
            const translatedReasonAllyin = await translateTextWithCache(comparison.reason_allyin, 'ar');
            const translatedReasonChatgpt = await translateTextWithCache(comparison.reason_chatgpt, 'ar');
            
            setTranslatedComparison({
              reason_allyin: translatedReasonAllyin,
              reason_chatgpt: translatedReasonChatgpt
            });
          }

          // Translate scoreResults if it exists and not already translated
          if (scoreResults && !translatedScoreResults) {
            console.log('Translating scoreResults to Arabic...');
            const translatedResults = await translateScoreResults(scoreResults);
            setTranslatedScoreResults(translatedResults);
          }
        } catch (error) {
          console.error('Translation error:', error);
          setTranslatedComparison(comparison);
          setTranslatedScoreResults(scoreResults);
        } finally {
          setIsTranslating(false);
        }
      } else {
        // For English, use original data immediately
        setTranslatedComparison(null);
        setTranslatedScoreResults(null);
        setIsTranslating(false);
      }
    };

    // Only trigger translation when language changes or when new data arrives
    if ((uiLanguage === 'ar' && (comparison || scoreResults)) || uiLanguage === 'en') {
      handleTranslation();
    }
  }, [uiLanguage]);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      setCriterion(initialCriterion || '');
    } else {
      console.log(`[ScoreContractsMode] Resetting state due to dependency change. Mode: ${mode}, Workspace: ${workspaceName}, InitialCriterion: "${initialCriterion}"`);
      setCriterion('');
      setMaxScore(5);
      setScoreResults(null);
      setComparison(null);
      setError('');
      setAdminComment('');
      // Reset final scores when workspace changes
      setFinalOpenrouterScores({});
      setFinalChatgptScores({});
      // Reset translation states
      setTranslatedComparison(null);
      setTranslatedScoreResults(null);
      setTranslationCache({});
    }
  }, [initialCriterion, workspaceName, mode, compareResponsesEnabled, shareDataWithChatgpt]); // Added shareDataWithChatgpt to dependencies

  // NEW EFFECT: Initialize final scores when scoreResults change
  useEffect(() => {
    if (scoreResults) {
      console.log('[ScoreContractsMode] scoreResults updated:', scoreResults);
      console.log('[ScoreContractsMode] final_scores_openrouter:', scoreResults.final_scores_openrouter);
      console.log('[ScoreContractsMode] final_scores_chatgpt:', scoreResults.final_scores_chatgpt);
      
      setFinalOpenrouterScores(scoreResults.final_scores_openrouter || {});
      setFinalChatgptScores(scoreResults.final_scores_chatgpt || {});
    }
  }, [scoreResults]);

  // NEW FUNCTION: Handle matrix updates and recalculate final scores
  const handleMatrixUpdate = async (matrixType) => {
    console.log(`[ScoreContractsMode] Matrix ${matrixType} was updated, recalculating final scores...`);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/workspace/${workspaceName}/current-scores`);
      if (!response.ok) {
        throw new Error('Failed to fetch updated scores');
      }
      
      const data = await response.json();
      console.log(`[ScoreContractsMode] Received data from backend:`, data);
      
      // Update the final scores state
      setFinalOpenrouterScores(data.final_scores_openrouter || {});
      setFinalChatgptScores(data.final_scores_chatgpt || {});
      
      console.log(`[ScoreContractsMode] Updated state with:`, {
        finalOpenrouterScores: data.final_scores_openrouter || {},
        finalChatgptScores: data.final_scores_chatgpt || {}
      });
      
      // Also update the raw contract data in scoreResults so individual tables stay in sync
      if (scoreResults) {
        setScoreResults(prev => ({
          ...prev,
          raw_openrouter: data.raw_openrouter,
          raw_chatgpt: data.raw_chatgpt,
          final_scores_openrouter: data.final_scores_openrouter,
          final_scores_chatgpt: data.final_scores_chatgpt
        }));
      }
      
      console.log(`[ScoreContractsMode] Final scores updated successfully`);
      
    } catch (error) {
      console.error('Error recalculating final scores:', error);
      alert('Failed to update final scores. Please try again.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    setScoreResults(null);
    setComparison(null);
    setAdminComment('');
    setJobId(null);

    try {
      // Always use async mode (no timeout)
      const { data } = await scoreContracts(criterion, workspaceName, maxScore, compareResponsesEnabled, shareDataWithChatgpt, true);
      
      if (data.job_id) {
        setJobId(data.job_id);
        // Start polling for job completion (no UI feedback needed)
        pollJobStatus(data.job_id);
      } else {
        // Fallback to synchronous mode if no job_id returned
        setScoreResults(data);
        setFinalOpenrouterScores(data.final_scores_openrouter || {});
        setFinalChatgptScores(data.final_scores_chatgpt || {});
        setSuccess('Contracts scored successfully! Results are now saved and available.');
        setLoading(false);

        if (compareResponsesEnabled) {
          const openrouterResultString = JSON.stringify(data.final_scores_openrouter, null, 2);
          const chatgptResultString = JSON.stringify(data.final_scores_chatgpt, null, 2);

          if (openrouterResultString && chatgptResultString) {
            try {
              const compRes = await compareResponses(openrouterResultString, chatgptResultString);
              setComparison(compRes.data);
            } catch (compErr) {
              console.error('Error comparing scoring results:', compErr);
            }
          }
        }
      }

    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to score contracts.'
      );
      setLoading(false);
    }
  };

  const handleSubmitToAdmin = async () => {
    setLoading(true);
    try {
      console.log("[handleSubmitToAdmin] Exporting report before submitting...");

      // Step 1: Export the report
      const response = await exportReport(workspaceName);
      const blob = new Blob([response.data]);

      // Step 2: Upload the report to the expected DAG path via backend
      const formData = new FormData();
      formData.append('file', blob, `${workspaceName}_evaluation_report.xlsx`);
      formData.append('workspace', workspaceName);

      const uploadResp = await fetch(`${BACKEND_URL}/api/upload-report`, {
        method: 'POST',
        body: formData
      });

      if (!uploadResp.ok) {
        const errorText = await uploadResp.text();
        console.error("Upload failed with response:", errorText);
        throw new Error("Failed to upload report to backend.");
      }

      // Step 3: Submit to admin
      console.log("[handleSubmitToAdmin] Submitting to admin...");
      await submitAdmin(workspaceName, adminComment, mode);
      alert("Submitted to admin successfully!");
    } catch (err) {
      console.error("Error during report upload or submission:", err);
      alert(
        err.response?.data?.detail ||
        err.message ||
        "Failed to submit to admin."
      );
    } finally {
      setLoading(false);
    }
  };

  // Corrected: Ensure this explicitly sets .xlsx
  const handleExportReport = async () => {
    setLoading(true);
    try {
      const response = await exportReport(workspaceName, uiLanguage);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const langSuffix = uiLanguage === 'ar' ? '_arabic' : '';
      link.setAttribute('download', `${workspaceName}_evaluation_report${langSuffix}.xlsx`); // CHANGED TO .xlsx
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      alert("Report exported successfully!");
    } catch (err) {
      console.error("Error exporting report:", err);
      alert(`Failed to export report: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };


  const renderAdminApprovalCard = () => (
    <div className="card" style={{ marginTop: '2em', padding: '1.5em', borderRadius: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5em' }}>
        <div style={{ width: 12, height: 12, backgroundColor: '#f9f9f9', borderRadius: '3px', marginRight: 10 }}></div>
        <h4 className="card-title" style={{ margin: 0 }}>Submit for Admin Approval</h4>
      </div>

      <p className="small-text" style={{ marginBottom: '1em' }}>
        Technical evaluation complete. Ready for final review and decision.
      </p>

      <textarea
        placeholder="Add comments for the admin reviewer (optional)..."
        rows="3"
        className="input-field"
        disabled={loading}
        value={adminComment}
        onChange={(e) => setAdminComment(e.target.value)}
      />

      <div style={{ display: 'flex', gap: '1em' }}>
        <button
          className="button"
          style={{
            backgroundColor: '#6366f1',
            color: '#fff',
            padding: '0.5em 1.5em',
            borderRadius: '6px',
            border: 'none'
          }}
          onClick={handleSubmitToAdmin}
          disabled={!scoreResults || loading}
        >
          Submit to Admin
        </button>
        <button
          className="button export-btn"
          style={{
            backgroundColor: 'var(--color-accent)',
            color: '#181a20',
            padding: '0.5em 1.5em',
            borderRadius: '6px',
            border: 'none',
            fontWeight: '700',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
          onClick={handleExportReport}
          disabled={!scoreResults || loading}
        >
          💾 Export Report
        </button>
      </div>
    </div>
  );

  return (
    <div className="score-contracts-mode">
      <div className="section-wrapper">
        <div className="card">
          <h3 className="card-title">Configure Evaluation</h3>
          
          {/* Language Slider */}
          <div style={{ marginBottom: '1rem', padding: '0.5rem 0', borderBottom: '1px solid var(--color-border)' }}>
            <label className="small-text" style={{ marginBottom: '0.5rem', display: 'block' }}>Display Language:</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span className="small-text" style={{ color: uiLanguage === 'en' ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}>English</span>
              <div 
                className="language-toggle"
                onClick={() => !loading && setUiLanguage(uiLanguage === 'en' ? 'ar' : 'en')}
                style={{
                  position: 'relative',
                  width: '60px',
                  height: '24px',
                  backgroundColor: 'var(--color-border)',
                  borderRadius: '12px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  transition: 'background-color 0.3s ease',
                  opacity: loading ? 0.6 : 1
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: '2px',
                    left: uiLanguage === 'en' ? '2px' : '34px',
                    width: '20px',
                    height: '20px',
                    backgroundColor: 'white',
                    borderRadius: '50%',
                    transition: 'left 0.3s ease',
                    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.2)'
                  }}
                />
              </div>
              <span className="small-text" style={{ color: uiLanguage === 'ar' ? 'var(--color-primary)' : 'var(--color-text-secondary)' }}>العربية</span>
            </div>
          </div>

          
          <form onSubmit={handleSubmit}>
            <textarea
              id="criterion-input"
              value={criterion}
              onChange={(e) => {
              setCriterion(e.target.value);
              setSuccess(''); // Clear success message when criterion changes
            }}
              rows={3}
              placeholder="Enter evaluation criterion:"
              disabled={loading}
              style={{ 
                marginBottom: '1em',
                width: '100%',
                minHeight: '80px',
                fontSize: '1rem',
                lineHeight: '1.5'
              }}
            />
            <div className="score-input-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
              <label htmlFor="max-score-input" className="small-text" style={{ fontWeight: 500, color: '#4b5563' }}>
                Score (e.g., 5 or 10):
              </label>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <input
                  type="number"
                  id="max-score-input"
                  value={maxScore}
                  onChange={(e) => {
              setMaxScore(parseInt(e.target.value));
              setSuccess(''); // Clear success message when max score changes
            }}
                  min="1"
                  max="10"
                  disabled={loading}
                  className="score-input"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="evaluate-button"
                >
                  {loading ? (
                    <>
                      <span className="spinner" style={{ marginRight: '8px' }}></span>
                      Evaluating...
                    </>
                  ) : (
                    <>
                      <span className="evaluate-icon">▶</span> Evaluate
                    </>
                  )}
                </button>

              </div>
            </div>
          </form>
          
         
        </div>
      </div>

      {loading && progressSteps?.length > 0 && (
        <div
          className="card loading-progress-box"
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            flexDirection: 'column',
            padding: '2rem',
            textAlign: 'center',
            width: '100%',
            marginBottom: '2rem'
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


      <div className="section-wrapper">
        <div className="card">
          <div className="upload-section">
            <FileUpload
              workspaceName={workspaceName}
              fileType="documents"
              onUploadSuccess={() => console.log("Documents uploaded")}
            />
          </div>
          <div className="upload-section">
            <FileUpload
              workspaceName={workspaceName}
              fileType="criteria"
              onUploadSuccess={() => console.log("Criteria uploaded")}
            />
          </div>
        </div>
      </div>
  
      {error && (
        <div className="section-wrapper">
          <p className="error-message">Error: {error}</p>
        </div>
      )}

      {success && (
        <div className="section-wrapper">
          <p className="success-message">✅ {success}</p>
        </div>
      )}
  
      {scoreResults && (
        <>
          {isTranslating && uiLanguage === 'ar' ? (
            <div className="section-wrapper">
              <div className="card" style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                <h4>Translating scoring results to Arabic...</h4>
                <p>Please wait while we translate all the contract evaluations.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="section-wrapper">
                <ScoringMatrixPivoted
                  contracts={translatedScoreResults?.raw_openrouter?.contracts || scoreResults.raw_openrouter?.contracts}
                  title="Allyin Breakdown"
                  workspaceName={workspaceName}
                  loading={loading}
                  setLoading={setLoading}
                  type="openrouter"
                  onUpdate={() => handleMatrixUpdate('openrouter')}
                  uiLanguage={uiLanguage} // Pass language for RTL support
                />
              </div>
      
              <div className="section-wrapper">
                <ScoringMatrixPivoted
                  contracts={translatedScoreResults?.raw_chatgpt?.contracts || scoreResults.raw_chatgpt?.contracts}
                  title="ChatGPT Breakdown"
                  workspaceName={workspaceName}
                  loading={loading}
                  setLoading={setLoading}
                  type="chatgpt"
                  onUpdate={() => handleMatrixUpdate('chatgpt')}
                  uiLanguage={uiLanguage} // Pass language for RTL support
                />
              </div>
      
              <div className="section-wrapper">
                <FinalScoresTable
                  workspaceName={workspaceName}
                  initialOpenrouterScores={finalOpenrouterScores}
                  initialChatgptScores={finalChatgptScores}
                  compareResponsesEnabled={compareResponsesEnabled}
                  loading={loading}
                  setLoading={setLoading}
                  uiLanguage={uiLanguage} // Pass language for RTL support
                />
              </div>
      
              {scoreResults.summary_of_best && (
                <div className="section-wrapper">
                  <BestProposalSummary
                    workspaceName={workspaceName}
                    initialSummary={translatedScoreResults?.summary_of_best || scoreResults.summary_of_best}
                    loading={loading}
                    setLoading={setLoading}
                    uiLanguage={uiLanguage} // Pass language for RTL support
                  />
                </div>
              )}
            </>
          )}
  
          {compareResponsesEnabled && comparison && (
            <div className="section-wrapper">
              <div className="comparison-results-card card">
                <h4 className="card-title">AI Scoring Result Comparison:</h4>
                {isTranslating && uiLanguage === 'ar' ? (
                  <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                    <small>Translating to Arabic...</small>
                  </div>
                ) : (
                  <div dir={uiLanguage === 'ar' ? 'rtl' : 'ltr'} style={{ textAlign: uiLanguage === 'ar' ? 'right' : 'left' }}>
                    <p><strong>Allyin's Reason:</strong> {translatedComparison?.reason_allyin || comparison.reason_allyin}</p>
                    <p><strong>ChatGPT's Reason:</strong> {translatedComparison?.reason_chatgpt || comparison.reason_chatgpt}</p>
                  </div>
                )}
              </div>
            </div>
          )}
  
          <div className="section-wrapper">
            {renderAdminApprovalCard()}
          </div>
        </>
      )}
    </div>
  );
  }
  
  export default ScoreContractsMode;