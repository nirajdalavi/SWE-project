// frontend/src/components/AskQuestionMode/index.jsx
import React, { useState, useEffect } from 'react';
import { askQuestion, compareResponses, translateText, getJobStatus } from '../../services/api';
import PdfViewerComponent from '../PdfViewerComponent';

function AskQuestionMode({ workspaceName, initialQuestion, compareResponsesEnabled, shareDataWithChatgpt, useWebSearch, specificUrl, responseSize, responseType, onOpenPdfSource, mode, setLoading, loading, progressSteps,
  setProgressSteps, currentStepIndex, setCurrentStepIndex }) {
  const [question, setQuestion] = useState(initialQuestion || '');
  const [openrouterAnswer, setOpenrouterAnswer] = useState('');
  const [chatgptAnswer, setChatgptAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [error, setError] = useState('');
  const [comparison, setComparison] = useState(null);
  const [openrouterTime, setOpenrouterTime] = useState(null);
  const [chatgptTime, setChatgptTime] = useState(null);
  const [openedPdfSourceInternal, setOpenedPdfSourceInternal] = useState(null);
  const [uiLanguage, setUiLanguage] = useState('en'); // UI language state
  const [translationCache, setTranslationCache] = useState({}); // Cache translations
  const [translatedOpenrouterAnswer, setTranslatedOpenrouterAnswer] = useState('');
  const [translatedChatgptAnswer, setTranslatedChatgptAnswer] = useState('');
  const [isTranslating, setIsTranslating] = useState(false); // Track translation progress
  
  // Async job states
  const [jobId, setJobId] = useState(null);
  
  const allSteps = [
    "Understanding the question...",
    "Finding relevant documents...",
    "Generating response..."
  ];

  // Polling function for job status
  const pollJobStatus = async (jobId, maxAttempts = 600, pollInterval = 3000) => {
    let attempts = 0;
    
    const poll = async () => {
      try {
        attempts++;
        const response = await getJobStatus(jobId);
        const job = response.data;
        
        // Check if job is complete
        if (job.status === 'SUCCESS') {
          const result = job.result;
          
          setOpenrouterAnswer(result.answers.openrouter);
          setSources(result.sources);
          setOpenrouterTime(result.answers.response_time?.openrouter);
          
          if (compareResponsesEnabled) {
            setChatgptAnswer(result.answers.chatgpt);
            setChatgptTime(result.answers.response_time?.chatgpt);
            
            if (result.answers.openrouter && result.answers.chatgpt) {
              try {
                const compRes = await compareResponses(result.answers.openrouter, result.answers.chatgpt);
                setComparison(compRes.data);
              } catch (compErr) {
                console.error('Error comparing responses:', compErr);
              }
            }
          }
          
          setCurrentStepIndex(2);
          setLoading(false);
          setJobId(null);
        } else if (job.status === 'FAILURE') {
          setError(job.error || 'Question processing failed');
          setLoading(false);
          setJobId(null);
        } else if (job.status === 'NOT_FOUND') {
          setError('Job not found');
          setLoading(false);
          setJobId(null);
        } else {
          // Continue polling if job is still in progress
          if (attempts < maxAttempts) {
            setTimeout(poll, pollInterval);
          } else {
            setError('Job polling timeout');
            setLoading(false);
            setJobId(null);
          }
        }
      } catch (error) {
        setError('Error checking job status: ' + error.message);
        setLoading(false);
        setJobId(null);
      }
    };
    
    // Start polling
    poll();
  };

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

  // Handle translation when language changes
  useEffect(() => {
    const handleTranslation = async () => {
      // Only translate if we have content and Arabic is selected
      if (uiLanguage === 'ar') {
        setIsTranslating(true);
        try {
          if (openrouterAnswer) {
            const translated = await translateTextWithCache(openrouterAnswer, 'ar');
            setTranslatedOpenrouterAnswer(translated);
          }
          if (chatgptAnswer) {
            const translated = await translateTextWithCache(chatgptAnswer, 'ar');
            setTranslatedChatgptAnswer(translated);
          }
        } catch (error) {
          console.error('Translation error:', error);
          // Fallback to original text
          setTranslatedOpenrouterAnswer(openrouterAnswer);
          setTranslatedChatgptAnswer(chatgptAnswer);
        } finally {
          setIsTranslating(false);
        }
      } else {
        // For English, use original answers directly
        setTranslatedOpenrouterAnswer(openrouterAnswer);
        setTranslatedChatgptAnswer(chatgptAnswer);
        setIsTranslating(false);
      }
    };

    // Only run translation if we have answers to translate
    if (openrouterAnswer || chatgptAnswer) {
      handleTranslation();
    }
  }, [uiLanguage, openrouterAnswer, chatgptAnswer]);

  useEffect(() => {
    setQuestion(initialQuestion || '');
    setOpenrouterAnswer('');
    setChatgptAnswer('');
    setTranslatedOpenrouterAnswer('');
    setTranslatedChatgptAnswer('');
    setSources([]);
    setError('');
    setComparison(null);
    setOpenrouterTime(null);
    setChatgptTime(null);
    setOpenedPdfSourceInternal(null);
    setProgressSteps(allSteps);
    setCurrentStepIndex(0);
  }, [initialQuestion, workspaceName, mode, compareResponsesEnabled, shareDataWithChatgpt, useWebSearch, specificUrl]); // Added shareDataWithChatgpt, useWebSearch, and specificUrl to dependencies

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setOpenrouterAnswer('');
    setChatgptAnswer('');
    setSources([]);
    setComparison(null);
    setOpenrouterTime(null);
    setChatgptTime(null);
    setOpenedPdfSourceInternal(null);
    setProgressSteps(allSteps);
    setCurrentStepIndex(0);
    setJobId(null);

    try {
      await new Promise((r) => setTimeout(r, 300));
      setCurrentStepIndex(1);

      // Always use async mode (no timeout)
      const res = await askQuestion(question, workspaceName, responseSize, responseType, compareResponsesEnabled, shareDataWithChatgpt, useWebSearch, specificUrl, true);
      
      if (res.data.job_id) {
        setJobId(res.data.job_id);
        // Start polling for job completion
        pollJobStatus(res.data.job_id);
      } else {
        // Fallback to synchronous mode if no job_id returned
        setCurrentStepIndex(2);

        setOpenrouterAnswer(res.data.answers.openrouter);
        console.log('Sources received:', res.data.sources);
        setSources(res.data.sources);
        setOpenrouterTime(res.data.answers.response_time?.openrouter);

        if (compareResponsesEnabled) {
          setChatgptAnswer(res.data.answers.chatgpt);
          setChatgptTime(res.data.answers.response_time?.chatgpt);

          if (res.data.answers.openrouter && res.data.answers.chatgpt) {
            try {
              const compRes = await compareResponses(res.data.answers.openrouter, res.data.answers.chatgpt);
              setComparison(compRes.data);
            } catch (compErr) {
              console.error('Error comparing responses:', compErr);
            }
          }
        } else {
          setChatgptAnswer('');
          setComparison(null);
          setChatgptTime(null);
        }
        setLoading(false);
      }
      
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to get answer. Make sure documents are uploaded and embedded.'
      );
      setLoading(false);
    }
  };

  const handleSourceClick = (source) => {
    setOpenedPdfSourceInternal(source);
  };

  const handleClosePdfViewerInternal = () => {
    setOpenedPdfSourceInternal(null);
  };

  return (
    <div className="ask-question-mode">
      <div className="card">
        <h3 className="card-title">Ask a Question</h3>
        
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
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows="3"
            placeholder="Enter your question about the contracts..."
            disabled={loading}
            style={{
              width: '100%',
              minHeight: '80px',
              fontSize: '1rem',
              lineHeight: '1.5'
            }}
          />
          {/* Removed the shareDataWithChatgpt toggle from here as it's now in App.js */}
          <button type="submit" disabled={loading} className="evaluate-button">
            {loading ? (
              <>
                <span className="spinner" style={{ marginRight: '8px' }}></span>
                Thinking...
              </>
            ) : (
              <>
                <span className="evaluate-icon">▶</span> Submit
              </>
            )}
          </button>
        </form>
      </div>
  
      {error && (
        <p className="error-message">Error: {error}</p>
      )}
  
      {(openrouterAnswer || chatgptAnswer) && (
        <div className="dual-response">
          <div className="response-box allyin">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              <img src="/logo.png" alt="Allyin Logo" style={{ width: '24px', height: '24px', flexShrink: 0 }} />
              <h4 className="response-title" style={{ margin: 0 }}>Allyin Response</h4>
            </div>
            <div 
              className="response-content" 
              dir={uiLanguage === 'ar' ? 'rtl' : 'ltr'}
              style={{ textAlign: uiLanguage === 'ar' ? 'right' : 'left' }}
            >
              {isTranslating && uiLanguage === 'ar' && openrouterAnswer && !translatedOpenrouterAnswer ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                  <small>Translating to Arabic...</small>
                </div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: translatedOpenrouterAnswer || openrouterAnswer }} />
              )}
            </div>
            {openrouterTime && (
              <div className="response-meta">
                <small>Response Time: {openrouterTime.toFixed(2)}s</small>
              </div>
            )}
          </div>
  
          {compareResponsesEnabled && (
            <div className="response-box chatgpt">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <img src="/ChatGPT-Logo-Advanced-Language-Generation-PNG-Transparent-Innovative-Design-jpg.webp" alt="ChatGPT Logo" style={{ width: '24px', height: '24px', flexShrink: 0 }} />
                <h4 className="response-title" style={{ margin: 0 }}>ChatGPT Response</h4>
              </div>
              <div 
                className="response-content" 
                dir={uiLanguage === 'ar' ? 'rtl' : 'ltr'}
                style={{ textAlign: uiLanguage === 'ar' ? 'right' : 'left' }}
              >
                {isTranslating && uiLanguage === 'ar' && chatgptAnswer && !translatedChatgptAnswer ? (
                  <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
                    <small>Translating to Arabic...</small>
                  </div>
                ) : (
                  <div dangerouslySetInnerHTML={{ __html: translatedChatgptAnswer || chatgptAnswer || 'No response (comparison disabled).' }} />
                )}
              </div>
              {chatgptTime && (
                <div className="response-meta">
                  <small>Response Time: {chatgptTime.toFixed(2)}s</small>
                </div>
              )}
            </div>
          )}
        </div>
      )}
  
      {sources.length > 0 && (
        <div className="sources-section card">
          <h4 className="card-title">Sources</h4>
          <div className="sources-list">
            {sources.map((source, index) => {
              // Check if this is a web source (has link property)
              console.log('Rendering source:', source);
              
              // Safety check for source object
              if (!source || typeof source !== 'object') {
                console.warn('Invalid source object:', source);
                return null;
              }
              
              const isWebSource = source.link && source.link.startsWith('http');
              
              if (isWebSource) {
                // Handle web sources
                return (
                  <div key={index} className="source-item-card">
                    <div className="source-item-content">
                      <div className="source-icon">🌐</div>
                      <div className="source-text">
                        <div className="source-title">{source.title || 'Web Source'}</div>
                        {source.description && (
                          <div className="source-description">{source.description}</div>
                        )}
                        <div className="source-url">
                          {source.exact_page_url ? (
                            <a href={source.exact_page_url} target="_blank" rel="noopener noreferrer">
                              {source.exact_page_url}
                            </a>
                          ) : (
                            <a href={source.link} target="_blank" rel="noopener noreferrer">
                              {source.link}
                            </a>
                          )}
                        </div>
                        
                        {/* Show relevant sections from the website */}
                        {source.relevant_sections && source.relevant_sections.length > 0 && (
                          <div className="relevant-sections">
                            <div className="sections-title">
                              {source.source_type === 'crawled_website' 
                                ? `Relevant content from ${source.metadata?.pages_crawled || 'multiple'} pages:`
                                : 'Relevant content from this page:'
                              }
                            </div>
                            {source.relevant_sections.map((section, sectionIndex) => (
                              <div key={sectionIndex} className="section-item">
                                {section.page_url && section.page_url !== source.link && (
                                  <div className="section-source">
                                    📄 From: <a href={section.page_url} target="_blank" rel="noopener noreferrer" className="section-link">
                                      {section.page_title || section.page_url}
                                    </a>
                                  </div>
                                )}
                                <div className="section-text">{section.text}</div>
                                <div className="section-relevance">
                                  Relevance: {Math.round(section.relevance_score * 100)}%
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {source.extracted_from && (
                          <div className="extraction-info">{source.extracted_from}</div>
                        )}
                      </div>
                    </div>
                    <a 
                      href={source.link} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="button secondary"
                    >
                      Visit Website
                    </a>
                  </div>
                );
              } else {
                // Handle document sources (existing logic)
                const filePath = source.file || '';
                const isFromResumes = filePath.includes('resumes/');
                const isFromContracts = filePath.includes('contracts/');
                const isFromJobDescriptions = filePath.includes('job_descriptions/');
                
                // Get just the filename without path
                const fileName = filePath ? filePath.split('/').pop() : 'Unknown file';
                
                // Create a friendly display name
                let displayName = fileName;
                if (isFromResumes) {
                  displayName = `Resume: ${fileName}`;
                } else if (isFromJobDescriptions) {
                  displayName = `Job Description: ${fileName}`;
                } else if (isFromContracts) {
                  displayName = `Contract: ${fileName}`;
                }
                
                return (
                  <div key={index} className="source-item-card">
                    <div className="source-item-content">
                      <div className="source-icon">📄</div>
                      <span className="source-text">{displayName} (Page: {source.page})</span>
                    </div>
                    <button onClick={() => handleSourceClick(source)} className="button secondary">View PDF</button>
                  </div>
                );
              }
            })}
          </div>
  
          {openedPdfSourceInternal && (
            <div className="pdf-viewer-card card" style={{ marginTop: '1rem' }}>
              <PdfViewerComponent
                workspaceName={workspaceName}
                fileName={openedPdfSourceInternal.file}
                initialPage={openedPdfSourceInternal.page}
                onClose={handleClosePdfViewerInternal}
              />
            </div>
          )}
        </div>
      )}
  
      {compareResponsesEnabled && comparison && (
        <div className="comparison-results-card card">
          <h4 className="card-title">AI Response Comparison:</h4>
          <p><strong>Allyin's Reason:</strong> {comparison.reason_allyin}</p>
          <p><strong>ChatGPT's Reason:</strong> {comparison.reason_chatgpt}</p>
        </div>
      )}
    </div>
  );
}

export default AskQuestionMode;