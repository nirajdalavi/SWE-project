// frontend/src/components/AuditMode.js
import React, { useState, useEffect } from 'react';
import { performAudit, getAuditResults, getJobStatus } from '../services/api';
import FileUpload from './FileUpload';
import './AuditMode.css';

import { getBackendBaseUrl } from '../utils/apiUtils';

const BACKEND_URL = getBackendBaseUrl();

function AuditMode({ workspaceName, setLoading, loading }) {
  const [auditResults, setAuditResults] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isExpanded, setIsExpanded] = useState({});
  const [hasContracts, setHasContracts] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedReport, setEditedReport] = useState('');
  
  // Async job states
  const [jobId, setJobId] = useState(null);

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
          setAuditResults(job.result);
          setSuccess('Contract audit completed successfully!');
          
          // Auto-expand main sections (level 2) and keep sub-sections (level 3) collapsed
          const sections = parseAuditReport(job.result.audit_report);
          const autoExpanded = {};
          sections.forEach(section => {
            if (section.level === 2) {
              autoExpanded[section.id] = true;
            } else if (section.level === 3) {
              autoExpanded[section.id] = false;
            }
          });
          setIsExpanded(autoExpanded);
          
          setLoading(false);
          setJobId(null);
        } else if (job.status === 'FAILURE') {
          setError(job.error || 'Contract audit failed');
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

  // Check if contracts exist and load existing audit results when component loads
  useEffect(() => {
    if (workspaceName) {
      // Assume contracts exist if we have a workspace (they can be uploaded)
      setHasContracts(true);
      
      // Load existing audit results if they exist
      loadExistingAuditResults();
    }
  }, [workspaceName]);

  // Function to load existing audit results
  const loadExistingAuditResults = async () => {
    try {
      const response = await getAuditResults(workspaceName);
      setAuditResults(response.data);
      setSuccess('Previous audit results loaded.');
      
      // Auto-expand main sections and keep sub-sections collapsed
      const sections = parseAuditReport(response.data.audit_report);
      const autoExpanded = {};
      sections.forEach(section => {
        if (section.level === 2) {
          autoExpanded[section.id] = true;
        } else if (section.level === 3) {
          autoExpanded[section.id] = false;
        }
      });
      setIsExpanded(autoExpanded);
    } catch (err) {
      // No existing results found - this is normal for new workspaces
      console.log('No existing audit results found');
    }
  };

  // Function to toggle section expansion
  const toggleSection = (sectionId) => {
    setIsExpanded(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId]
    }));
  };

  // Function to expand all sections
  const expandAllSections = () => {
    if (!auditResults) return;
    const sections = parseAuditReport(auditResults.audit_report);
    const allExpanded = {};
    sections.forEach(section => {
      if (section.level === 3) { // Only expand sub-sections
        allExpanded[section.id] = true;
      }
    });
    setIsExpanded(allExpanded);
  };

  // Function to collapse all sections
  const collapseAllSections = () => {
    if (!auditResults) return;
    const sections = parseAuditReport(auditResults.audit_report);
    const allCollapsed = {};
    sections.forEach(section => {
      if (section.level === 3) { // Only collapse sub-sections
        allCollapsed[section.id] = false;
      }
    });
    setIsExpanded(allCollapsed);
  };

  // Function to enter edit mode
  const enterEditMode = () => {
    setIsEditing(true);
    setEditedReport(auditResults.audit_report);
  };

  // Function to exit edit mode
  const exitEditMode = () => {
    setIsEditing(false);
    setEditedReport('');
  };

  // Function to save edited report
  const saveEditedReport = () => {
    if (!editedReport.trim()) {
      setError('Report cannot be empty');
      return;
    }

    // Update the audit results with edited content
    const updatedResults = {
      ...auditResults,
      audit_report: editedReport,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      edited: true
    };

    setAuditResults(updatedResults);
    setIsEditing(false);
    setEditedReport('');
    setSuccess('Report updated successfully!');
    
    // Clear success message after 3 seconds
    setTimeout(() => setSuccess(''), 3000);
  };

  // Function to format the audit report into sections
  const parseAuditReport = (reportText) => {
    const sections = [];
    const lines = reportText.split('\n');
    let currentSection = null;
    let currentContent = [];

    for (const line of lines) {
      // Check if line is a section header (starts with ## or ###)
      if (line.match(/^#{2,3}\s+(.+)/)) {
        // Save previous section if exists
        if (currentSection) {
          sections.push({
            id: currentSection.id,
            title: currentSection.title,
            level: currentSection.level,
            content: currentContent.join('\n').trim()
          });
        }
        
        // Start new section
        const match = line.match(/^(#{2,3})\s+(.+)/);
        const level = match[1].length;
        const title = match[2].trim().replace(/:\s*$/, ''); // Remove trailing colon
        const id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        
        currentSection = { id, title, level };
        currentContent = [];
      } else if (currentSection) {
        currentContent.push(line);
      }
    }

    // Add the last section
    if (currentSection) {
      sections.push({
        id: currentSection.id,
        title: currentSection.title,
        level: currentSection.level,
        content: currentContent.join('\n').trim()
      });
    }

    return sections;
  };

  const handleAudit = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    setAuditResults(null);
    setJobId(null);

    try {
      // Always use async mode (no timeout)
      const { data } = await performAudit(workspaceName, true);
      
      if (data.job_id) {
        setJobId(data.job_id);
        // Start polling for job completion
        pollJobStatus(data.job_id);
      } else {
        // Fallback to synchronous mode if no job_id returned
        setAuditResults(data);
        setSuccess('Contract audit completed successfully!');
        
        // Auto-expand main sections (level 2) and keep sub-sections (level 3) collapsed
        const sections = parseAuditReport(data.audit_report);
        const autoExpanded = {};
        sections.forEach(section => {
          if (section.level === 2) {
            autoExpanded[section.id] = true;
          } else if (section.level === 3) {
            autoExpanded[section.id] = false;
          }
        });
        setIsExpanded(autoExpanded);
        setLoading(false);
      }
      
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to perform contract audit.'
      );
      setLoading(false);
    }
  };

  const formatContent = (content) => {
    if (!content) return '';
    
    // Split content into paragraphs and format
    return content.split('\n\n').map((paragraph, index) => {
      if (paragraph.trim() === '') return null;
      
      // Check if paragraph contains bullet points
      if (paragraph.includes('•') || paragraph.includes('-') || paragraph.includes('*')) {
        const lines = paragraph.split('\n');
        return (
          <div key={index} className="audit-paragraph">
            {lines.map((line, lineIndex) => {
              if (line.trim().startsWith('•') || line.trim().startsWith('-') || line.trim().startsWith('*')) {
                const bulletText = line.trim().substring(1).trim();
                // Apply bold formatting to bullet points
                const formattedText = bulletText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                return (
                  <div key={lineIndex} className="audit-bullet-point" dangerouslySetInnerHTML={{ __html: formattedText }} />
                );
              } else if (line.trim()) {
                const formattedText = line.trim().replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                return (
                  <div key={lineIndex} className="audit-text-line" dangerouslySetInnerHTML={{ __html: formattedText }} />
                );
              }
              return null;
            })}
          </div>
        );
      }
      
      // Regular paragraph
      const formattedParagraph = paragraph.trim().replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return (
        <div key={index} className="audit-paragraph" dangerouslySetInnerHTML={{ __html: formattedParagraph }} />
      );
    }).filter(Boolean);
  };

  // Function to download PDF report
  const downloadPDFReport = () => {
    // Create a new window with the report content
    const reportWindow = window.open('', '_blank');
    
    // Get the current date for the report
    const currentDate = new Date().toLocaleDateString();
    
    // Create HTML content for the PDF
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Contract Audit Report - ${workspaceName}</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 40px;
            color: #333;
          }
          .header {
            text-align: center;
            border-bottom: 2px solid #667eea;
            padding-bottom: 20px;
            margin-bottom: 30px;
          }
          .header h1 {
            color: #667eea;
            margin: 0;
            font-size: 28px;
          }
          .header p {
            margin: 10px 0 0 0;
            color: #666;
            font-size: 14px;
          }
          .summary {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
          }
          .summary h3 {
            margin-top: 0;
            color: #333;
          }
          .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
          }
          .summary-item {
            display: flex;
            flex-direction: column;
          }
          .summary-label {
            font-weight: bold;
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
          }
          .summary-value {
            color: #333;
            font-size: 16px;
            margin-top: 5px;
          }
          .contracts-list {
            margin-top: 15px;
          }
          .contracts-list h4 {
            margin-bottom: 10px;
            color: #333;
          }
          .contracts-list ul {
            margin: 0;
            padding-left: 20px;
          }
          .contracts-list li {
            margin-bottom: 5px;
          }
          .report-content {
            margin-top: 30px;
          }
          .section {
            margin-bottom: 25px;
            page-break-inside: avoid;
          }
          .section-title {
            color: #667eea;
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 8px;
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 3px;
          }
          .section-content {
            line-height: 1.6;
            margin-top: 5px;
          }
          .section-content p {
            margin-bottom: 8px;
            margin-top: 0;
          }
          .section-content ul {
            margin-bottom: 8px;
            margin-top: 0;
            padding-left: 20px;
          }
          .section-content li {
            margin-bottom: 4px;
          }
          .section-content strong {
            font-weight: bold;
            color: #333;
          }
          .footer {
            margin-top: 50px;
            text-align: center;
            color: #666;
            font-size: 12px;
            border-top: 1px solid #e9ecef;
            padding-top: 20px;
          }
          @media print {
            body { margin: 20px; }
            .section { page-break-inside: avoid; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>Contract Audit Report</h1>
          <p>Workspace: ${auditResults.workspace_name} | Generated: ${currentDate}</p>
        </div>
        
        <div class="summary">
          <h3>Audit Summary</h3>
          <div class="summary-grid">
            <div class="summary-item">
              <span class="summary-label">Workspace</span>
              <span class="summary-value">${auditResults.workspace_name}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Contracts Analyzed</span>
              <span class="summary-value">${auditResults.contracts_analyzed}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Processing Time</span>
              <span class="summary-value">${auditResults.processing_time?.total_time}s</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Completed</span>
              <span class="summary-value">${auditResults.timestamp}</span>
            </div>
          </div>
          
          <div class="contracts-list">
            <h4>Contracts Analyzed:</h4>
            <ul>
              ${auditResults.contract_names?.map(name => `<li>${name}</li>`).join('')}
            </ul>
          </div>
        </div>
        
        <div class="report-content">
          ${parseAuditReport(auditResults.audit_report).map(section => `
            <div class="section">
              <div class="section-title">${section.title}</div>
              <div class="section-content">
                ${formatContentForPDF(section.content)}
              </div>
            </div>
          `).join('')}
        </div>
        
        <div class="footer">
          <p>Generated by Aqeed.ai Contract Audit System</p>
          <p>Report ID: ${auditResults.timestamp}</p>
        </div>
      </body>
      </html>
    `;
    
    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
    
    // Wait for content to load, then print
    setTimeout(() => {
      reportWindow.print();
    }, 500);
  };

  // Helper function to format content for PDF
  const formatContentForPDF = (content) => {
    if (!content) return '';
    
    // Split content into lines for better processing
    const lines = content.split('\n');
    let formatted = '';
    let inList = false;
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (!line) {
        // Empty line - close list if we're in one, add paragraph break
        if (inList) {
          formatted += '</ul>';
          inList = false;
        }
        formatted += '<br>';
        continue;
      }
      
      // Check if line is a bullet point or list item
      if (line.match(/^[•\-*]\s+(.+)/) || line.match(/^\d+\.\s+(.+)/)) {
        if (!inList) {
          formatted += '<ul>';
          inList = true;
        }
        const listItem = line.replace(/^[•\-*]\s+/, '').replace(/^\d+\.\s+/, '');
        // Apply bold formatting to list items
        const boldFormatted = listItem.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted += `<li>${boldFormatted}</li>`;
      } else {
        // Regular text line
        if (inList) {
          formatted += '</ul>';
          inList = false;
        }
        
        // Apply bold formatting
        const boldFormatted = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formatted += `<p>${boldFormatted}</p>`;
      }
    }
    
    // Close any remaining list
    if (inList) {
      formatted += '</ul>';
    }
    
    return formatted;
  };

  return (
    <div className="audit-mode">
      <div className="audit-header">
        <h2 className="audit-title">Contract Audit Mode</h2>
        <p className="audit-description">
          Perform a comprehensive audit of all contracts in your workspace. 
          Get detailed insights on terms, risks, compliance, and recommendations.
        </p>
      </div>

      <div className="audit-controls">
        <button 
          className="audit-button"
          onClick={handleAudit}
          disabled={loading}
        >
          {loading ? 'Performing Audit...' : '🔍 Start Contract Audit'}
        </button>
        {!hasContracts && !auditResults && (
          <p className="audit-help-text">
            Upload contract documents above to perform an audit
          </p>
        )}
      </div>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {success && (
        <div className="success-message">
          <strong>Success:</strong> {success}
        </div>
      )}

      {/* File Upload Section */}
      <div className="file-upload-card card">
       
        <FileUpload
          key="upload-contracts-audit"
          workspaceName={workspaceName}
          fileType="documents"
          onUploadSuccess={() => {
            setSuccess('Contracts uploaded successfully! You can now perform an audit.');
            setAuditResults(null); // Clear previous results
            setHasContracts(true); // Mark that contracts are available
          }}
        />
      </div>

      {auditResults && (
        <div className="audit-results">
          <div className="audit-summary">
            <h3>Audit Summary</h3>
            <div className="summary-stats">
              <div className="stat-item">
                <span className="stat-label">Workspace:</span>
                <span className="stat-value">{auditResults.workspace_name}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Contracts Analyzed:</span>
                <span className="stat-value">{auditResults.contracts_analyzed}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Processing Time:</span>
                <span className="stat-value">{auditResults.processing_time?.total_time}s</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Completed:</span>
                <span className="stat-value">{auditResults.timestamp}</span>
              </div>
            </div>
            
            <div className="contracts-list">
              <h4>Contracts Analyzed:</h4>
              <ul>
                {auditResults.contract_names?.map((name, index) => (
                  <li key={index}>{name}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="audit-report">
            <h3>Detailed Audit Report</h3>
            
            {isEditing ? (
              <div className="audit-edit-mode">
                <div className="edit-header">
                  <h4>✏️ Edit Report</h4>
                  <p>You can modify the report content below. Use markdown formatting for best results.</p>
                </div>
                <textarea
                  className="audit-edit-textarea"
                  value={editedReport}
                  onChange={(e) => setEditedReport(e.target.value)}
                  placeholder="Enter your audit report here..."
                  rows={20}
                />
                <div className="edit-actions">
                  <button 
                    className="action-button primary"
                    onClick={saveEditedReport}
                  >
                    💾 Save Changes
                  </button>
                  <button 
                    className="action-button secondary"
                    onClick={exitEditMode}
                  >
                    ❌ Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                {parseAuditReport(auditResults.audit_report).map((section) => (
                  <div key={section.id} className="audit-section">
                    {section.level === 2 ? (
                      // Main sections (##) - show content only if it exists
                      <>
                        <div className="audit-section-header main-section">
                          <h4 className="section-title">
                            {section.title}
                          </h4>
                        </div>
                        {section.content && section.content.trim() && (
                          <div className="audit-section-content">
                            {formatContent(section.content)}
                          </div>
                        )}
                      </>
                    ) : (
                      // Sub-sections (###) - collapsible with toggle
                      <>
                        <div 
                          className="audit-section-header sub-section"
                          onClick={() => toggleSection(section.id)}
                        >
                          <h4 className="section-title">
                            {section.title}
                          </h4>
                          <span className="expand-icon">
                            {isExpanded[section.id] ? '▼' : '▶'}
                          </span>
                        </div>
                        
                        {isExpanded[section.id] && (
                          <div className="audit-section-content">
                            {formatContent(section.content)}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="audit-actions">
            <button 
              className="action-button secondary"
              onClick={expandAllSections}
            >
              📖 Expand All
            </button>
            <button 
              className="action-button secondary"
              onClick={collapseAllSections}
            >
              📕 Collapse All
            </button>
            <button 
              className="action-button secondary"
              onClick={isEditing ? exitEditMode : enterEditMode}
            >
              {isEditing ? '❌ Cancel Edit' : '✏️ Edit Report'}
            </button>
            <button 
              className="action-button primary"
              onClick={downloadPDFReport}
            >
              📄 Download PDF Report
            </button>
          </div>
        </div>
      )}

      {loading && (
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
            marginTop: '2rem'
          }}
        >
          <h3>AI is performing contract audit...</h3>
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
            Please wait while the AI analyzes your contracts.<br />
            This may take 30-60 seconds depending on the number of contracts.
          </p>
        </div>
      )}
    </div>
  );
}

export default AuditMode;
