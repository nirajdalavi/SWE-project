// frontend/src/components/VendorRecommendationMode.js
import React, { useState, useEffect } from 'react';
import './VendorRecommendationMode.css';
import { FaFilePdf, FaEnvelope, FaExternalLinkAlt, FaLink, FaDatabase, FaLinkedin, FaGoogle, FaReddit, FaMapMarkerAlt, FaCalendarAlt, FaCheckCircle, FaChartLine } from 'react-icons/fa';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

import { getBackendBaseUrl } from '../utils/apiUtils';
import { getJobStatus } from '../services/api';

const BACKEND_URL = getBackendBaseUrl();

function VendorRecommendationMode({ workspaceName, setLoading, loading, showSidePanel, setShowSidePanel }) {
  const [formData, setFormData] = useState({
    project_requirements: '',
    industry: 'general',
    location_preference: 'any',
    vendor_count: 5,
    preference: 'balanced',
    vendor_type: 'auto', // 'auto', 'service_providers', 'technology_vendors', 'equipment_suppliers'
    enableRedditAnalysis: false,
    enableLinkedInAnalysis: false,
    enableGoogleReviews: false,
    enableOracleDB: false
  });
  
  const [recommendations, setRecommendations] = useState(() => {
    // Try to restore from localStorage on component mount
    const saved = localStorage.getItem(`vendor_recommendations_${workspaceName}`);
    return saved ? JSON.parse(saved) : null;
  });
  const [error, setError] = useState('');
  const [jobId, setJobId] = useState(null);
  const [selectedVendorTab, setSelectedVendorTab] = useState(() => {
    // Try to restore selected tab from localStorage
    const saved = localStorage.getItem(`selected_vendor_tab_${workspaceName}`);
    return saved ? parseInt(saved) : 0;
  });
  
  const [showRedditDiscussions, setShowRedditDiscussions] = useState(false);
  

  const [emailModal, setEmailModal] = useState(false);
  const [emailData, setEmailData] = useState({
    recipient_email: '',
    subject: 'Vendor Recommendations',
    message: 'Please find attached the vendor recommendations report.'
  });

  // New state for interest modal
  const [interestModal, setInterestModal] = useState(false);
  const [selectedVendor, setSelectedVendor] = useState(null);
  const [leadData, setLeadData] = useState({
    user_name: '',
    user_email: '',
    vendor_name: '',
    vendor_score: '',
    project_requirements: '',
    source: ''
  });

  // Persist recommendations to localStorage
  useEffect(() => {
    if (recommendations) {
      localStorage.setItem(`vendor_recommendations_${workspaceName}`, JSON.stringify(recommendations));
    }
  }, [recommendations, workspaceName]);

  // Persist selected vendor tab to localStorage
  useEffect(() => {
    localStorage.setItem(`selected_vendor_tab_${workspaceName}`, selectedVendorTab.toString());
  }, [selectedVendorTab, workspaceName]);

  // Function to clear stored recommendations
  const clearStoredRecommendations = () => {
    localStorage.removeItem(`vendor_recommendations_${workspaceName}`);
    localStorage.removeItem(`selected_vendor_tab_${workspaceName}`);
    setRecommendations(null);
    setSelectedVendorTab(0);
    setError('');
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const pollJobStatus = async (jobId, maxAttempts = 600, pollInterval = 3000) => {
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const response = await getJobStatus(jobId);
        const job = response.data;
        
        if (job.status === 'SUCCESS') {
          return job.result;
        } else if (job.status === 'FAILURE') {
          throw new Error(job.error || 'Job failed');
        } else if (job.status === 'PENDING' || job.status === 'PROCESSING') {
          // Continue polling
          attempts++;
          if (attempts >= maxAttempts) {
            throw new Error('Job polling timeout');
          }
          await new Promise(resolve => setTimeout(resolve, pollInterval));
        } else {
          throw new Error(`Unknown job status: ${job.status}`);
        }
      } catch (error) {
        if (attempts >= maxAttempts - 1) {
          throw error;
        }
        attempts++;
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }
    }
    
    throw new Error('Job polling timeout');
  };




  const handleEmailInputChange = (e) => {
    const { name, value } = e.target;
    setEmailData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleInterestClick = (vendor) => {
    setSelectedVendor(vendor);
    setLeadData({
      user_name: '',
      user_email: '',
      vendor_name: vendor.vendor_name,
      vendor_score: vendor.recommendation_score.toString(),
      project_requirements: formData.project_requirements,
      industry: formData.industry,
      location_preference: formData.location_preference
    });
    setInterestModal(true);
  };

  const handleLeadInputChange = (e) => {
    const { name, value } = e.target;
    setLeadData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const submitLeadInterest = async () => {
    if (!leadData.user_name.trim()) {
      alert('Please enter your name.');
      return;
    }
    
    if (!leadData.user_email.trim()) {
      alert('Please enter your email address.');
      return;
    }

    try {
      setLoading(true);
      
      const response = await fetch(`${BACKEND_URL}/submit-lead-interest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...leadData,
          workspace_name: workspaceName
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      alert('Thank you for your interest!');
      setInterestModal(false);
      setLeadData({
        user_name: '',
        user_email: '',
        vendor_name: '',
        vendor_score: '',
        project_requirements: '',
        source: ''
      });
    } catch (err) {
      console.error('Error submitting lead interest:', err);
      alert('Failed to submit interest. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setRecommendations(null);
    setJobId(null);

    try {
      const response = await fetch(`${BACKEND_URL}/vendor-recommendations?async_mode=true`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...formData,
          workspace_name: workspaceName,
          enable_reddit_analysis: formData.enableRedditAnalysis,
          enable_linkedin_analysis: formData.enableLinkedInAnalysis,
          enable_google_reviews: formData.enableGoogleReviews
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.job_id) {
        setJobId(data.job_id);
        const result = await pollJobStatus(data.job_id);
        setRecommendations(result);
      } else {
        setRecommendations(data);
      }
    } catch (err) {
      console.error('Error fetching vendor recommendations:', err);
      setError('Failed to get vendor recommendations. Please try again.');
    } finally {
      setLoading(false);
      setJobId(null);
    }
  };

  const exportToPDF = async () => {
    if (!recommendations) return;

    try {
      // Create a temporary div to render the content
      const tempDiv = document.createElement('div');
      tempDiv.style.position = 'absolute';
      tempDiv.style.left = '-9999px';
      tempDiv.style.top = '0';
      tempDiv.style.width = '800px';
      tempDiv.style.backgroundColor = 'white';
      tempDiv.style.padding = '20px';
      tempDiv.style.fontFamily = 'Arial, sans-serif';
      tempDiv.style.fontSize = '12px';
      tempDiv.style.color = 'black';
      
      // Generate HTML content for PDF
      tempDiv.innerHTML = `
        <div style="text-align: center; margin-bottom: 30px;">
          <h1 style="color: #2b78e4; margin-bottom: 10px;">Vendor Recommendations Report</h1>
          <p style="color: #666; font-size: 14px;">Generated on ${new Date().toLocaleDateString()}</p>
        </div>
        
        <div style="margin-bottom: 30px;">
          <h2 style="color: #333; border-bottom: 2px solid #2b78e4; padding-bottom: 5px;">Project Summary</h2>
          <p style="line-height: 1.6;">${recommendations.summary}</p>
        </div>
        
        <div>
          <h2 style="color: #333; border-bottom: 2px solid #2b78e4; padding-bottom: 5px;">Vendor Recommendations</h2>
          ${recommendations.recommendations.map((vendor, index) => `
            <div style="margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="color: #2b78e4; margin: 0;">${index + 1}. ${vendor.vendor_name}</h3>
                <div style="background: #2b78e4; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold;">
                  Score: ${vendor.recommendation_score}/10
                </div>
              </div>
              
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div><strong>Company Size:</strong> ${vendor.company_size}</div>
                <div><strong>Specialization:</strong> ${vendor.specialization}</div>
                <div><strong>Experience:</strong> ${vendor.experience}</div>
                <div><strong>Location:</strong> ${vendor.location}</div>
                <div><strong>Website:</strong> ${vendor.website || 'N/A'}</div>
              </div>
              
              <div style="margin-bottom: 15px;">
                <h4 style="color: #333; margin-bottom: 5px;">Strengths:</h4>
                <ul style="margin: 0; padding-left: 20px;">
                  ${vendor.strengths.map(strength => `<li>${strength}</li>`).join('')}
                </ul>
              </div>
              
              <div style="margin-bottom: 15px;">
                <h4 style="color: #333; margin-bottom: 5px;">Risk Factors:</h4>
                <ul style="margin: 0; padding-left: 20px;">
                  ${vendor.risk_factors.map(risk => `<li>${risk}</li>`).join('')}
                </ul>
              </div>
              
              <div>
                <h4 style="color: #333; margin-bottom: 5px;">Why Recommended:</h4>
                <p style="line-height: 1.6; margin: 0;">${vendor.rationale}</p>
              </div>
            </div>
          `).join('')}
        </div>
      `;
      
      document.body.appendChild(tempDiv);
      
      // Convert to canvas and then to PDF
      const canvas = await html2canvas(tempDiv, {
        scale: 2,
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#ffffff'
      });
      
      document.body.removeChild(tempDiv);
      
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const imgWidth = 210;
      const pageHeight = 295;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;
      
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
      
      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }
      
      // Download the PDF
      pdf.save(`${workspaceName}_vendor_recommendations.pdf`);
      
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Error generating PDF. Please try again.');
    }
  };

  const sendEmail = async () => {
    if (!emailData.recipient_email.trim()) {
      alert('Please enter a recipient email address.');
      return;
    }

    try {
      setLoading(true);
      
      const response = await fetch(`${BACKEND_URL}/send-vendor-email/${workspaceName}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(emailData)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      alert('Email sent successfully!');
      setEmailModal(false);
      setEmailData({
        recipient_email: '',
        subject: 'Vendor Recommendations',
        message: 'Please find attached the vendor recommendations report.'
      });
    } catch (err) {
      console.error('Error sending email:', err);
      alert('Failed to send email. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const industryOptions = [
    { value: 'general', label: 'General' },
    { value: 'technology', label: 'Technology' },
    { value: 'healthcare', label: 'Healthcare' },
    { value: 'finance', label: 'Finance' },
    { value: 'construction', label: 'Construction' },
    { value: 'manufacturing', label: 'Manufacturing' },
    { value: 'retail', label: 'Retail' },
    { value: 'education', label: 'Education' },
    { value: 'government', label: 'Government' },
    { value: 'nonprofit', label: 'Non-Profit' }
  ];


  const preferenceOptions = [
    { value: 'balanced', label: 'Balanced (Technical + Cost)' },
    { value: 'technical_competence', label: 'Technical Competence (Best-in-class solutions)' },
    { value: 'cost_effective', label: 'Cost Effective (Best value for money)' }
  ];


  return (
    <div className={`vendor-recommendation-mode ${showSidePanel ? 'with-side-panel' : ''}`}>
      <div className="section-wrapper">
        <div className="card">
          <h2 className="card-title">Vendor Recommendations</h2>
          <p className="card-description">
            Get AI-powered vendor recommendations based on your project requirements
          </p>
          
          <form onSubmit={handleSubmit} className="vendor-form">
            <div className="form-group">
              <label htmlFor="project_requirements" className="form-label">
                Project Requirements *
              </label>
              <textarea
                id="project_requirements"
                name="project_requirements"
                value={formData.project_requirements}
                onChange={handleInputChange}
                placeholder="Describe your project requirements in detail. Include technical specifications, business needs, and any specific constraints..."
                className="form-textarea"
                rows="4"
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label htmlFor="industry" className="form-label">
                  Industry
                </label>
                <select
                  id="industry"
                  name="industry"
                  value={formData.industry}
                  onChange={handleInputChange}
                  className="form-select"
                >
                  {industryOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="location_preference" className="form-label">
                  Location Preference
                </label>
                <input
                  type="text"
                  id="location_preference"
                  name="location_preference"
                  value={formData.location_preference}
                  onChange={handleInputChange}
                  placeholder="e.g., North America, Europe, Asia, or 'any'"
                  className="form-input"
                />
              </div>
            </div>


            <div className="form-row">
              <div className="form-group">
                <label htmlFor="preference" className="form-label">
                  Scoring Preference
                </label>
                <select
                  id="preference"
                  name="preference"
                  value={formData.preference}
                  onChange={handleInputChange}
                  className="form-select"
                >
                  {preferenceOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="vendor_count" className="form-label">
                  Number of Vendors
                </label>
                <input
                  type="number"
                  id="vendor_count"
                  name="vendor_count"
                  value={formData.vendor_count}
                  onChange={handleInputChange}
                  min="1"
                  max="20"
                  placeholder="5"
                  className="form-input"
                />
              </div>
            </div>

            {/* Deep Analysis Toggle Switches */}
            <div className="form-group">
              <label className="form-label">
                Deep Analysis
              </label>
              <p style={{ 
                fontSize: '0.9rem', 
                color: '#666', 
                marginBottom: '1rem',
                fontStyle: 'italic'
              }}>
                Enable external data sources for enhanced vendor analysis
              </p>
              
              <div style={{ 
                display: 'flex', 
                gap: '1rem',
                padding: '0.5rem 0',
                flexWrap: 'wrap'
              }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.75rem',
                  flex: 1
                }}>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={formData.enableRedditAnalysis}
                      onChange={(e) => setFormData(prev => ({ ...prev, enableRedditAnalysis: e.target.checked }))}
                      disabled={loading}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                    <FaReddit style={{ color: '#FF4500', fontSize: '1.2rem' }} />
                    <span className="form-label" style={{ margin: 0, flex: 1 }}>
                      Reddit Analysis
                    </span>
                  </div>
                </div>
                
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.75rem',
                  flex: 1
                }}>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={formData.enableLinkedInAnalysis}
                      onChange={(e) => setFormData(prev => ({ ...prev, enableLinkedInAnalysis: e.target.checked }))}
                      disabled={loading}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                    <FaLinkedin style={{ color: '#0077B5', fontSize: '1.2rem' }} />
                    <span className="form-label" style={{ margin: 0, flex: 1 }}>
                      LinkedIn Analysis
                    </span>
                  </div>
                </div>

                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.75rem',
                  flex: 1
                }}>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={formData.enableGoogleReviews}
                      onChange={(e) => setFormData(prev => ({ ...prev, enableGoogleReviews: e.target.checked }))}
                      disabled={loading}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                    <FaGoogle style={{ color: '#4285F4', fontSize: '1.2rem' }} />
                    <span className="form-label" style={{ margin: 0, flex: 1 }}>
                      Google Reviews
                    </span>
                  </div>
                </div>

                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.75rem',
                  flex: 1
                }}>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={formData.enableOracleDB}
                      onChange={(e) => setFormData(prev => ({ ...prev, enableOracleDB: e.target.checked }))}
                      disabled={loading}
                    />
                    <span className="toggle-slider round"></span>
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                    <FaDatabase style={{ color: '#FF0000', fontSize: '1.2rem' }} />
                    <span className="form-label" style={{ margin: 0, flex: 1 }}>
                      Oracle Database
                    </span>
                  </div>
                </div>
              </div>
              
              {(formData.enableRedditAnalysis || formData.enableLinkedInAnalysis || formData.enableGoogleReviews || formData.enableOracleDB) && (
                <div style={{
                  padding: '0.75rem',
                  backgroundColor: '#e8f4fd',
                  border: '1px solid #bee5eb',
                  borderRadius: '6px',
                  fontSize: '0.85rem',
                  color: '#0c5460',
                  marginTop: '0.75rem'
                }}>
                  <strong>Active sources:</strong> {
                    [
                      formData.enableRedditAnalysis && 'Reddit',
                      formData.enableLinkedInAnalysis && 'LinkedIn',
                      formData.enableGoogleReviews && 'Google Reviews',
                      formData.enableOracleDB && 'Oracle DB'
                    ].filter(Boolean).join(', ')
                  }
                </div>
              )}
            </div>


            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1.5rem' }}>
              <button
                type="submit"
                disabled={loading || !formData.project_requirements.trim()}
                className="evaluate-button"
                style={{ 
                  padding: '1rem 2rem',
                  fontSize: '1.1rem',
                  minWidth: '200px',
                  height: '50px'
                }}
              >
                {loading ? 'AI is getting recommendations...' : 'Get Recommendations'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {loading && (
        <div className="section-wrapper">
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
        </div>
      )}

      {error && (
        <div className="section-wrapper">
          <p className="error-message">Error: {error}</p>
        </div>
      )}

      {recommendations && !loading && (
        <>
          {/* Deep Vendor Analysis Header */}
          <div className="section-wrapper">
            <div className="card">
              <div className="deep-analysis-header">
                <div className="header-content">
                  <h1 className="main-title">Deep Vendor Analysis</h1>
                  <p className="subtitle">Comprehensive analysis across all data sources</p>
                  {recommendations && (
                    <div className="results-indicator">
                      <span className="indicator-dot"></span>
                      Results loaded from previous session
                    </div>
                  )}
                </div>
                <div className="header-actions">
                  <button
                    className="export-button"
                    onClick={exportToPDF}
                  >
                    <FaFilePdf /> Export All Reports
                  </button>
                  <button
                    className="email-button"
                    onClick={() => setEmailModal(true)}
                  >
                    <FaEnvelope /> Email Analysis
                  </button>
                  <button
                    className="clear-button"
                    onClick={clearStoredRecommendations}
                    title="Clear stored results and start fresh"
                  >
                    Clear Results
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Vendor Tabs */}
          <div className="vendor-tabs-section">
            <div className="vendor-tabs-container">
                {recommendations.recommendations
                  .sort((a, b) => b.recommendation_score - a.recommendation_score)
                  .slice(0, 3)
                  .map((vendor, index) => (
                    <div
                      key={index}
                      className={`vendor-tab ${selectedVendorTab === index ? 'active' : ''}`}
                      onClick={() => setSelectedVendorTab(index)}
                    >
                      <div className="vendor-tab-content">
                        <h3 className="vendor-tab-name">{vendor.vendor_name}</h3>
                        <div className="vendor-tab-score">
                          <span className="score-number">{vendor.recommendation_score}</span>
                          <span className="score-separator">/</span>
                          <span className="score-total">10</span>
                        </div>
                        {index === 0 && (
                          <div className="recommended-badge">Recommended</div>
                        )}
                      </div>
                    </div>
                  ))}
            </div>
          </div>

          {/* Selected Vendor Details */}
          {(() => {
            const selectedVendor = recommendations.recommendations
              .sort((a, b) => b.recommendation_score - a.recommendation_score)
              [selectedVendorTab];
            
            if (!selectedVendor) return null;

            return (
              <div className="section-wrapper">
                <div className="card">
                  <div className="vendor-details-header">
                    <div className="vendor-details-title">
                      <h2 className="vendor-name">{selectedVendor.vendor_name}</h2>
                      <div className="vendor-recommendation-container">
                        <div className="recommended-badge-only">Recommended</div>
                        <div className="vendor-score-display">{selectedVendor.recommendation_score}/10</div>
                      </div>
                    </div>
                    <div className="vendor-website-link">
                      {selectedVendor.website && selectedVendor.website !== "N/A" && (
                        <a 
                          href={selectedVendor.website} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="visit-website-btn"
                        >
                          <span>Visit Website</span> <FaExternalLinkAlt />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Key Information */}
                  <div className="vendor-key-info">
                    <div className="info-item">
                      <div className="info-icon">
                        <FaMapMarkerAlt />
                      </div>
                      <div className="info-content">
                        <span className="info-label">Location</span>
                        <span className="info-value">{selectedVendor.location}</span>
                      </div>
                    </div>
                    <div className="info-item">
                      <div className="info-icon">
                        <FaCalendarAlt />
                      </div>
                      <div className="info-content">
                        <span className="info-label">Experience</span>
                        <span className="info-value">{selectedVendor.experience}</span>
                      </div>
                    </div>
                    <div className="info-item">
                      <div className="info-icon">
                        <FaCheckCircle />
                      </div>
                      <div className="info-content">
                        <span className="info-label">Company Size</span>
                        <span className="info-value">{selectedVendor.company_size}</span>
                      </div>
                    </div>
                    <div className="info-item">
                      <div className="info-icon">
                        <FaChartLine />
                      </div>
                      <div className="info-content">
                        <span className="info-label">Specialization</span>
                        <span className="info-value">{selectedVendor.specialization}</span>
                      </div>
                    </div>
                  </div>
                </div>

                  {/* Why Recommended */}
                  <div className="why-recommended-section">
                    <h3 className="section-title">
                      <span className="section-icon">✓</span>
                      Why Recommended
                    </h3>
                    <p className="recommendation-text">{selectedVendor.rationale}</p>
                  </div>

                  {/* Competitive Advantages & Risk Factors */}
                  <div className="advantages-risks-container">
                    <div className="competitive-advantages">
                      <h3 className="section-title">
                        <FaChartLine className="section-icon" />
                        Competitive Advantages
                      </h3>
                      <ul className="advantages-list">
                        {selectedVendor.strengths.map((strength, idx) => (
                          <li key={idx} className="advantage-item">
                            <span className="checkmark">✓</span>
                            {strength}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="risk-factors">
                      <h3 className="section-title">
                        <span className="section-icon">⚠</span>
                        Risk Factors
                      </h3>
                      <ul className="risks-list">
                        {selectedVendor.risk_factors.map((risk, idx) => (
                          <li key={idx} className="risk-item">
                            <span className="warning">⚠</span>
                            {risk}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Deep Analysis Section */}
                  <div className="deep-analysis-section">
                    <h3 className="section-title">Deep Analysis</h3>
                    <p className="section-subtitle">Based on external data sources</p>
                    
                    <div className="analysis-sources">
                      {formData.enableRedditAnalysis && (
                        <div className="analysis-source">
                          <h4 className="source-title">
                            <FaReddit className="source-icon" />
                            Reddit Community
                          </h4>
                          <div className="reddit-insight-block">
                            <p className="source-summary">
                              {selectedVendor.deep_analysis?.reddit_insights || "Reddit analysis unavailable - API may not be configured or vendor not discussed on Reddit"}
                            </p>
                          </div>
                          
                          {selectedVendor.external_data?.reddit?.mentions && selectedVendor.external_data.reddit.mentions.length > 0 && (
                            <div className="reddit-discussions">
                              <button 
                                className="discussions-toggle"
                                onClick={() => setShowRedditDiscussions(!showRedditDiscussions)}
                              >
                                <h5 className="discussions-title">
                                  Recent Discussions ({selectedVendor.external_data.reddit.mentions.length})
                                  <span className="dropdown-icon">{showRedditDiscussions ? '▲' : '▼'}</span>
                                </h5>
                              </button>
                              {showRedditDiscussions && (
                                <div className="discussions-list">
                                  {selectedVendor.external_data.reddit.mentions.slice(0, 4).map((post, index) => (
                                    <div key={index} className="discussion-item">
                                      <div className="discussion-header">
                                        <span className="discussion-score">{post.score} ↑</span>
                                        <span className="discussion-sentiment positive">positive</span>
                                      </div>
                                      <a 
                                        href={post.url} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="discussion-link"
                                      >
                                        {post.title}
                                      </a>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {formData.enableGoogleReviews && (
                        <div className="analysis-source">
                          <h4 className="source-title">
                            <FaGoogle className="source-icon" />
                            Google Reviews
                          </h4>
                          <div className="google-reviews-info">
                            {selectedVendor.external_data?.google_places?.rating_info ? (
                              <>
                                <span className="rating">
                                  ⭐ {selectedVendor.external_data.google_places.rating_info.overall_rating || 'N/A'}
                                </span>
                                <span className="reviews-count">
                                  ({selectedVendor.external_data.google_places.rating_info.total_reviews || 0} reviews)
                                </span>
                                <span className={`sentiment-tag ${selectedVendor.external_data.google_places.sentiment_analysis?.overall_sentiment || 'neutral'}`}>
                                  {selectedVendor.external_data.google_places.sentiment_analysis?.overall_sentiment || 'neutral'} sentiment
                                </span>
                              </>
                            ) : (
                              <>
                                <span className="rating">4.7</span>
                                <span className="reviews-count">(43 reviews)</span>
                                <span className="sentiment-tag positive">Positive</span>
                              </>
                            )}
                          </div>
                          
                          {/* Google Reviews Analysis Insights */}
                          {selectedVendor.deep_analysis?.google_reviews_insights && (
                            <div className="google-insights">
                              <div className="google-insights-block">
                                <p className="insights-text">{selectedVendor.deep_analysis.google_reviews_insights}</p>
                              </div>
                            </div>
                          )}
                          
                          {/* View Reviews Button */}
                          {selectedVendor.external_data?.google_places?.reviews && selectedVendor.external_data.google_places.reviews.length > 0 && (
                            <div className="more-reviews-link">
                              <a 
                                href={selectedVendor.external_data.google_places.place_id 
                                  ? `https://www.google.com/maps/place/?q=place_id:${selectedVendor.external_data.google_places.place_id}`
                                  : `https://www.google.com/maps/search/${encodeURIComponent(selectedVendor.external_data.google_places.place_info?.name || selectedVendor.vendor_name)}`
                                }
                                target="_blank"
                                rel="noopener noreferrer"
                                className="view-all-reviews-btn"
                              >
                                View All {selectedVendor.external_data.google_places.rating_info?.total_reviews || 0} Reviews
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div className="recommendations-section">
                    <h3 className="section-title">Recommendations</h3>
                    <p className="recommendations-text">
                      Based on our comprehensive analysis, we recommend considering {selectedVendor.vendor_name} for your project. 
                      Their expertise in {selectedVendor.specialization} and {selectedVendor.company_size} company size make them 
                      a strong candidate. However, consider the risk factors mentioned above and ensure proper project governance 
                      and cost management throughout the engagement.
                    </p>
                  </div>
              </div>
            );
          })()}

          {/* Citations Section */}
          {recommendations.citations && recommendations.citations.length > 0 && (
            <div className="section-wrapper">
              <div className="card">
                <h3 className="card-title">
                  <FaLink style={{ marginRight: '0.5rem', fontSize: '1.1rem' }} />
                  Sources & Citations
                </h3>
                <p className="card-description" style={{ marginBottom: '1rem' }}>
                  The following sources were used to generate these vendor recommendations:
                </p>
                
                <div className="citations-list">
                  {recommendations.citations.map((citation, index) => {
                    // Handle both structured citations and simple URL strings
                    const citationUrl = typeof citation === 'string' ? citation : citation.url;
                    const citationTitle = typeof citation === 'string' ? null : citation.title;
                    const citationSnippet = typeof citation === 'string' ? null : citation.snippet;
                    
                    // Generate initials from title or URL
                    const getInitials = (title, url) => {
                      if (title) {
                        const words = title.split(' ').filter(word => word.length > 0);
                        if (words.length >= 2) {
                          return (words[0][0] + words[1][0]).toUpperCase();
                        } else if (words.length === 1) {
                          return words[0].substring(0, 2).toUpperCase();
                        }
                      }
                      if (url) {
                        const domain = url.replace(/^https?:\/\//, '').replace(/^www\./, '');
                        const parts = domain.split('.');
                        if (parts.length >= 2) {
                          return parts[0].substring(0, 2).toUpperCase();
                        }
                      }
                      return 'SR';
                    };
                    
                    const initials = getInitials(citationTitle, citationUrl);
                    
                    return (
                      <div key={index} className="citation-item" style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '1rem',
                        border: '1px solid var(--color-border)',
                        borderRadius: '8px',
                        marginBottom: '0.75rem',
                        backgroundColor: 'var(--color-background)',
                        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
                      }}>
                        {/* Initials Circle */}
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '8px',
                          backgroundColor: '#f0f0f0',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          marginRight: '1rem',
                          flexShrink: 0,
                          fontWeight: 'bold',
                          fontSize: '0.9rem',
                          color: '#666'
                        }}>
                          {initials}
                        </div>
                        
                        {/* Content */}
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                            <h4 style={{ 
                              margin: 0, 
                              color: 'var(--color-text)', 
                              fontSize: '1rem',
                              fontWeight: '600'
                            }}>
                              {citationTitle || `Source ${index + 1}`}
                            </h4>
                                                         {citationUrl && (
                               <a 
                                 href={citationUrl} 
                                 target="_blank" 
                                 rel="noopener noreferrer"
                                 style={{
                                   color: '#666666',
                                   textDecoration: 'none',
                                   fontSize: '0.9rem',
                                   display: 'flex',
                                   alignItems: 'center'
                                 }}
                               >
                                 <FaExternalLinkAlt style={{ fontSize: '0.8rem' }} />
                               </a>
                             )}
                          </div>
                                                     {citationUrl && (
                             <p style={{ 
                               margin: '0.25rem 0 0 0', 
                               color: '#666666',
                               fontSize: '0.85rem',
                               wordBreak: 'break-all'
                             }}>
                               {citationUrl.replace(/^https?:\/\//, '').replace(/^www\./, '')}
                             </p>
                           )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Email Modal */}
      {emailModal && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--color-card)',
            padding: '2rem',
            borderRadius: '8px',
            width: '90%',
            maxWidth: '500px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{ marginBottom: '1.5rem', color: 'var(--color-text)' }}>Send Vendor Recommendations</h3>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--color-text)' }}>
                Recipient Email *
              </label>
              <input
                type="email"
                name="recipient_email"
                value={emailData.recipient_email}
                onChange={handleEmailInputChange}
                placeholder="Enter recipient email address"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-background)',
                  color: 'var(--color-text)'
                }}
                required
              />
            </div>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--color-text)' }}>
                Subject
              </label>
              <input
                type="text"
                name="subject"
                value={emailData.subject}
                onChange={handleEmailInputChange}
                placeholder="Email subject"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-background)',
                  color: 'var(--color-text)'
                }}
              />
            </div>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--color-text)' }}>
                Message
              </label>
              <textarea
                name="message"
                value={emailData.message}
                onChange={handleEmailInputChange}
                placeholder="Email message"
                rows="4"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-background)',
                  color: 'var(--color-text)',
                  resize: 'vertical'
                }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setEmailModal(false)}
                style={{
                  padding: '0.75rem 1.5rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'transparent',
                  color: 'var(--color-text)',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={sendEmail}
                disabled={loading || !emailData.recipient_email.trim()}
                className="evaluate-button"
                style={{ padding: '0.75rem 1.5rem' }}
              >
                {loading ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interest Modal */}
      {interestModal && (
        <div className="modal-overlay" style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000
        }}>
          <div className="modal-content" style={{
            backgroundColor: 'var(--color-card)',
            padding: '2rem',
            borderRadius: '8px',
            width: '90%',
            maxWidth: '400px',
            boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{ marginBottom: '1.5rem', color: 'var(--color-text)' }}>
              Interested in {selectedVendor?.vendor_name}?
            </h3>
            
            <p style={{ 
              marginBottom: '1.5rem', 
              color: 'var(--color-text)', 
              fontSize: '0.9rem',
              lineHeight: '1.5'
            }}>
              We'll share your interest with our team and get back to you with more details about this vendor.
            </p>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--color-text)' }}>
                Your Name *
              </label>
              <input
                type="text"
                name="user_name"
                value={leadData.user_name}
                onChange={handleLeadInputChange}
                placeholder="Enter your full name"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-background)',
                  color: 'var(--color-text)'
                }}
                required
              />
            </div>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--color-text)' }}>
                Your Email Address *
              </label>
              <input
                type="email"
                name="user_email"
                value={leadData.user_email}
                onChange={handleLeadInputChange}
                placeholder="Enter your email address"
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-background)',
                  color: 'var(--color-text)'
                }}
                required
              />
            </div>
            
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setInterestModal(false)}
                style={{
                  padding: '0.75rem 1.5rem',
                  border: '1px solid var(--color-border)',
                  borderRadius: '4px',
                  backgroundColor: 'transparent',
                  color: 'var(--color-text)',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={submitLeadInterest}
                disabled={loading || !leadData.user_name.trim() || !leadData.user_email.trim()}
                style={{
                  padding: '0.75rem 1.5rem',
                  border: 'none',
                  borderRadius: '4px',
                  backgroundColor: '#28a745',
                  color: 'white',
                  cursor: 'pointer',
                  fontWeight: '500'
                }}
              >
                {loading ? 'Submitting...' : 'Submit Interest'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Side Panel */}
      {showSidePanel && (
        <div className={`side-panel ${showSidePanel ? 'open' : ''}`}>
          <div className="side-panel-header">
            <h3>Sponsored Vendors</h3>
          </div>
          <div className="side-panel-content">
            {/* Alternate Vendors Section */}
            {recommendations && recommendations.alternate_vendors && recommendations.alternate_vendors.length > 0 ? (
              <div className="side-panel-section">
                <p className="section-subtitle">Explore additional options</p>
                <div className="alternate-vendors-list">
                  {recommendations.alternate_vendors.map((vendor, index) => (
                    <div key={index} className="alternate-vendor-card">
                      <div className="vendor-info">
                        <div className="vendor-name-container">
                          <h5 className="vendor-name">{vendor.vendor_name}</h5>
                          <span className="featured-badge">FEATURED</span>
                        </div>
                        <p className="vendor-domain">{vendor.domain}</p>
                        <div className="vendor-score">
                          <span className="score-label">Score:</span>
                          <span className="score-value">{vendor.recommendation_score}/10</span>
                        </div>
                      </div>
                      <button 
                        className="vendor-website-btn"
                        onClick={() => window.open(vendor.website, '_blank')}
                        disabled={!vendor.website || vendor.website === 'N/A'}
                      >
                        <FaExternalLinkAlt /> Visit Website
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="side-panel-section">
                <p className="section-subtitle">No alternate vendors available</p>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', margin: 0 }}>
                  Generate vendor recommendations to see alternative options here.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default VendorRecommendationMode;
