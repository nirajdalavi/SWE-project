// frontend/src/components/LegalMode.js
import React, { useState, useEffect } from 'react';
import { performLegalAnalysis, getLegalResults, getJobStatus } from '../services/api';
import FileUpload from './FileUpload';
import './LegalMode.css';

import { getBackendBaseUrl } from '../utils/apiUtils';

const BACKEND_URL = getBackendBaseUrl();

function LegalMode({ workspaceName, setLoading, loading }) {
  const [legalResults, setLegalResults] = useState(null);
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
          setLegalResults(job.result);
          setSuccess('Legal analysis completed successfully!');
          
          // Auto-expand main sections (level 2) and keep sub-sections (level 3) collapsed
          const sections = parseLegalReport(job.result.legal_analysis_report);
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
          setError(job.error || 'Legal analysis failed');
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

  // Check if contracts exist and load existing legal results when component loads
  useEffect(() => {
    if (workspaceName) {
      // Assume contracts exist if we have a workspace (they can be uploaded)
      setHasContracts(true);
      
      // Load existing legal results if they exist
      loadExistingLegalResults();
    }
  }, [workspaceName]);

  // Function to load existing legal results
  const loadExistingLegalResults = async () => {
    try {
      const response = await getLegalResults(workspaceName);
      setLegalResults(response.data);
      setSuccess('Previous legal analysis results loaded.');
      
      // Auto-expand main sections and keep sub-sections collapsed
      const sections = parseLegalReport(response.data.legal_analysis_report);
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
      console.log('No existing legal analysis results found');
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
    if (!legalResults) return;
    const sections = parseLegalReport(legalResults.legal_analysis_report);
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
    if (!legalResults) return;
    const sections = parseLegalReport(legalResults.legal_analysis_report);
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
    setEditedReport(legalResults.legal_analysis_report);
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

    // Update the legal results with edited content
    const updatedResults = {
      ...legalResults,
      legal_analysis_report: editedReport,
      timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
      edited: true
    };

    setLegalResults(updatedResults);
    setIsEditing(false);
    setEditedReport('');
    setSuccess('Report updated successfully!');
    
    // Clear success message after 3 seconds
    setTimeout(() => setSuccess(''), 3000);
  };

  // Function to format the legal report into sections
  const parseLegalReport = (reportText) => {
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
        // Clean the title by removing markdown formatting
        const rawTitle = match[2].trim().replace(/:\s*$/, ''); // Remove trailing colon
        const cleanTitle = rawTitle.replace(/\*\*(.*?)\*\*/g, '$1'); // Remove bold markdown
        const id = cleanTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        
        currentSection = { id, title: cleanTitle, level };
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

  const handleLegalAnalysis = async () => {
    setLoading(true);
    setError('');
    setSuccess('');
    setLegalResults(null);
    setJobId(null);

    try {
      // Always use async mode (no timeout)
      const { data } = await performLegalAnalysis(workspaceName, true);
      
      if (data.job_id) {
        setJobId(data.job_id);
        // Start polling for job completion
        pollJobStatus(data.job_id);
      } else {
        // Fallback to synchronous mode if no job_id returned
        setLegalResults(data);
        setSuccess('Legal analysis completed successfully!');
        
        // Auto-expand main sections (level 2) and keep sub-sections (level 3) collapsed
        const sections = parseLegalReport(data.legal_analysis_report);
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
        'Failed to perform legal analysis.'
      );
      setLoading(false);
    }
  };

  const formatContent = (content) => {
    if (!content) return '';
    
    // Helper function to clean markdown formatting
    const cleanMarkdown = (text) => {
      return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold text
        .replace(/\*(.*?)\*/g, '<em>$1</em>') // Italic text
        .replace(/`(.*?)`/g, '<code>$1</code>') // Code text
        .replace(/^#{1,6}\s+(.*)$/gm, '<strong>$1</strong>') // Headers
        .replace(/^\s*[-*+]\s+(.*)$/gm, '• $1') // Bullet points
        .replace(/^\s*\d+\.\s+(.*)$/gm, '$1') // Numbered lists
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Additional bold text cleanup
        .trim();
    };

    // Helper function to parse markdown tables
    const parseTable = (lines, startIndex) => {
      const tableLines = [];
      let i = startIndex;
      
      // Collect all table lines (lines with | separators)
      while (i < lines.length && lines[i].trim().includes('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }
      
      if (tableLines.length < 2) return null; // Need at least header and one data row
      
      // Parse header row
      const headerRow = tableLines[0].split('|').map(cell => cell.trim()).filter(cell => cell);
      
      // Skip separator row (contains dashes)
      const dataRows = tableLines.slice(2).map(row => 
        row.split('|').map(cell => cell.trim()).filter(cell => cell)
      );
      
      return {
        type: 'table',
        headers: headerRow,
        rows: dataRows,
        endIndex: i - 1
      };
    };
    
    // Split content into lines for better processing
    const lines = content.split('\n');
    const formattedLines = [];
    let currentParagraph = [];
    let i = 0;
    
    while (i < lines.length) {
      const line = lines[i].trim();
      
      if (!line) {
        // Empty line - end current paragraph if it exists
        if (currentParagraph.length > 0) {
          formattedLines.push({
            type: 'paragraph',
            content: currentParagraph.join('\n')
          });
          currentParagraph = [];
        }
        i++;
        continue;
      }
      
      // Check if line is a table (contains | separators)
      if (line.includes('|')) {
        // End current paragraph if it exists
        if (currentParagraph.length > 0) {
          formattedLines.push({
            type: 'paragraph',
            content: currentParagraph.join('\n')
          });
          currentParagraph = [];
        }
        
        // Parse table
        const table = parseTable(lines, i);
        if (table) {
          formattedLines.push(table);
          i = table.endIndex + 1;
        } else {
          // If not a valid table, treat as regular line
          currentParagraph.push(line);
          i++;
        }
        continue;
      }
      
      // Check if line is a sub-heading (starts with ### or ####)
      if (line.match(/^#{3,4}\s+(.+)/)) {
        // End current paragraph if it exists
        if (currentParagraph.length > 0) {
          formattedLines.push({
            type: 'paragraph',
            content: currentParagraph.join('\n')
          });
          currentParagraph = [];
        }
        
        // Add sub-heading
        const match = line.match(/^#{3,4}\s+(.+)/);
        const cleanTitle = match[1].replace(/\*\*(.*?)\*\*/g, '$1'); // Remove bold markdown
        formattedLines.push({
          type: 'subheading',
          content: cleanTitle
        });
        i++;
        continue;
      }
      
      // Check if line is a bullet point
      if (line.match(/^[-*+•]\s+(.+)/)) {
        // End current paragraph if it exists
        if (currentParagraph.length > 0) {
          formattedLines.push({
            type: 'paragraph',
            content: currentParagraph.join('\n')
          });
          currentParagraph = [];
        }
        
        // Add bullet point
        const match = line.match(/^[-*+•]\s+(.+)/);
        formattedLines.push({
          type: 'bullet',
          content: match[1]
        });
        i++;
        continue;
      }
      
      // Regular line - add to current paragraph
      currentParagraph.push(line);
      i++;
    }
    
    // Add final paragraph if it exists
    if (currentParagraph.length > 0) {
      formattedLines.push({
        type: 'paragraph',
        content: currentParagraph.join('\n')
      });
    }
    
    // Render formatted lines
    return formattedLines.map((item, index) => {
      if (item.type === 'subheading') {
        return (
          <div key={index} className="legal-subheading">
            <strong>{item.content}</strong>
          </div>
        );
      } else if (item.type === 'bullet') {
        const formattedText = cleanMarkdown(item.content);
        return (
          <div key={index} className="legal-bullet-point" dangerouslySetInnerHTML={{ __html: formattedText }} />
        );
      } else if (item.type === 'paragraph') {
        const formattedText = cleanMarkdown(item.content);
        return (
          <div key={index} className="legal-paragraph" dangerouslySetInnerHTML={{ __html: formattedText }} />
        );
      } else if (item.type === 'table') {
        return (
          <div key={index} className="legal-table-container">
            <table className="legal-table">
              <thead>
                <tr>
                  {item.headers.map((header, headerIndex) => (
                    <th key={headerIndex} className="legal-table-header">
                      {header.replace(/\*\*(.*?)\*\*/g, '$1')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {item.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="legal-table-row">
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="legal-table-cell">
                        {cell.replace(/\*\*(.*?)\*\*/g, '$1')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      return null;
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
        <title>Legal Analysis Report - ${workspaceName}</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 40px;
            color: #333;
          }
          .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 20px;
          }
          .header h1 {
            color: #667eea;
            margin: 0;
          }
          .header p {
            margin: 5px 0;
            color: #666;
          }
          .section {
            margin-bottom: 25px;
            page-break-inside: avoid;
          }
          .section h2 {
            color: #667eea;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
          }
          .section h3 {
            color: #555;
            margin-top: 20px;
          }
          .bullet-point {
            margin: 5px 0 5px 20px;
          }
          .highlight {
            background-color: #f0f8ff;
            padding: 15px;
            border-left: 4px solid #667eea;
            margin: 15px 0;
          }
          .table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
          }
          .table th, .table td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
          }
          .table th {
            background-color: #f5f5f5;
            font-weight: bold;
          }
          @media print {
            body { margin: 20px; }
            .section { page-break-inside: avoid; }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>Legal Analysis Report</h1>
          <p><strong>Workspace:</strong> ${workspaceName}</p>
          <p><strong>Generated:</strong> ${currentDate}</p>
          <p><strong>Contracts Analyzed:</strong> ${legalResults?.contracts_analyzed || 0}</p>
        </div>
        
        <div class="content">
          ${legalResults?.legal_analysis_report?.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>') || 'No legal analysis report available.'}
        </div>
      </body>
      </html>
    `;
    
    reportWindow.document.write(htmlContent);
    reportWindow.document.close();
    reportWindow.print();
  };

  return (
    <div className="legal-mode">
      <div className="legal-header">
        <h2 className="legal-title">Legal Analysis Mode</h2>
        <p className="legal-description">
          Comprehensive legal analysis of contracts to identify missing clauses, assess risks, 
          and provide recommendations for indemnity, penalty clauses, and compliance requirements.
        </p>
      </div>

      <div className="legal-controls">
        <button 
          className="legal-button"
          onClick={handleLegalAnalysis}
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="loading-spinner" style={{ marginRight: '8px' }}></span>
              Analyzing Contracts...
            </>
          ) : (
            '⚖️ Start Legal Analysis'
          )}
        </button>
        {!hasContracts && !legalResults && (
          <p className="legal-help-text">
            Upload contract documents below to perform legal analysis
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
          key="upload-contracts-legal"
          workspaceName={workspaceName}
          fileType="documents"
          onUploadSuccess={() => {
            setSuccess('Contracts uploaded successfully! You can now perform legal analysis.');
            setLegalResults(null); // Clear previous results
            setHasContracts(true); // Mark that contracts are available
          }}
        />
      </div>

      {legalResults && (
        <div className="legal-results">
          <div className="legal-summary">
            <h3>Legal Analysis Summary</h3>
            <div className="summary-stats">
              <div className="stat-item">
                <span className="stat-label">Workspace:</span>
                <span className="stat-value">{legalResults.workspace_name}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Contracts Analyzed:</span>
                <span className="stat-value">{legalResults.contracts_analyzed}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Processing Time:</span>
                <span className="stat-value">{legalResults.processing_time?.total_time}s</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Completed:</span>
                <span className="stat-value">{legalResults.timestamp}</span>
              </div>
            </div>
            
            <div className="contracts-list">
              <h4>Contracts Analyzed:</h4>
              <ul>
                {legalResults.contract_names?.map((name, index) => (
                  <li key={index}>{name}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="legal-report">
            <h3>Detailed Legal Analysis Report</h3>
            
            {isEditing ? (
              <div className="legal-edit-mode">
                <div className="edit-header">
                  <h4>✏️ Edit Report</h4>
                  <p>You can modify the report content below. Use markdown formatting for best results.</p>
                </div>
                <textarea
                  className="legal-edit-textarea"
                  value={editedReport}
                  onChange={(e) => setEditedReport(e.target.value)}
                  placeholder="Enter your legal analysis report here..."
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
                {parseLegalReport(legalResults.legal_analysis_report).map((section) => (
                  <div key={section.id} className="legal-section">
                    {section.level === 2 ? (
                      // Main sections (##) - show content only if it exists
                      <>
                        <div className="legal-section-header main-section">
                          <h4 className="section-title">
                            {section.title}
                          </h4>
                        </div>
                        {section.content && section.content.trim() && (
                          <div className="legal-section-content">
                            {formatContent(section.content)}
                          </div>
                        )}
                      </>
                    ) : (
                      // Sub-sections (###) - collapsible with toggle
                      <>
                        <div 
                          className="legal-section-header sub-section"
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
                          <div className="legal-section-content">
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

          <div className="legal-actions">
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
    </div>
  );
}

export default LegalMode;
