// frontend/src/components/VendorResearchMode.js .
import React, { useState } from 'react';
import './VendorResearchMode.css';
import { FaFilePdf, FaEnvelope, FaExternalLinkAlt, FaLink, FaDatabase, FaLinkedin, FaGoogle, FaReddit, FaSearch } from 'react-icons/fa';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

import { getBackendBaseUrl } from '../utils/apiUtils';
import { getJobStatus } from '../services/api';

const BACKEND_URL = getBackendBaseUrl();

function VendorResearchMode({ workspaceName, setLoading, loading, showSidePanel, setShowSidePanel }) {
  const [formData, setFormData] = useState({
    vendor_name: '',
    location: '',
    enableRedditAnalysis: false,
    enableLinkedInAnalysis: false,
    enableGoogleReviews: false
  });
  
  const [researchResult, setResearchResult] = useState(null);
  const [error, setError] = useState('');
  const [jobId, setJobId] = useState(null);
  

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
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
        } else if (job.status === 'NOT_FOUND') {
          throw new Error('Job not found');
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


  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.vendor_name.trim()) {
      setError('Please enter a vendor name.');
      return;
    }

    if (!formData.location.trim()) {
      setError('Please enter a location.');
      return;
    }

    if (!formData.enableRedditAnalysis && !formData.enableLinkedInAnalysis && !formData.enableGoogleReviews) {
      setError('Please enable at least one external source for analysis.');
      return;
    }

    try {
      setLoading(true);
      setError('');
      setResearchResult(null);
      setJobId(null);
      
      const response = await fetch(`${BACKEND_URL}/vendor-research?async_mode=true`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          vendor_name: formData.vendor_name,
          location: formData.location,
          workspace_name: workspaceName,
          enable_reddit_analysis: formData.enableRedditAnalysis,
          enable_linkedin_analysis: formData.enableLinkedInAnalysis,
          enable_google_reviews: formData.enableGoogleReviews
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.job_id) {
        setJobId(data.job_id);
        const result = await pollJobStatus(data.job_id);
        setResearchResult(result);
      } else {
        setResearchResult(data);
      }
    } catch (err) {
      setError('Network error. Please check your connection and try again.');
      console.error('Error:', err);
    } finally {
      setLoading(false);
      setJobId(null);
    }
  };

  const generatePDF = async () => {
    if (!researchResult) return;

    try {
      setLoading(true);
      const element = document.getElementById('research-results');
      const canvas = await html2canvas(element, {
        scale: 2,
        useCORS: true,
        allowTaint: true
      });
      
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

      pdf.save(`vendor-research-${formData.vendor_name.replace(/\s+/g, '-').toLowerCase()}.pdf`);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Error generating PDF. Please try again.');
    } finally {
      setLoading(false);
    }
  };



  return (
    <div className="vendor-research-mode">
      <div className="section-wrapper">
        <div className="card">
          <h2 className="card-title">Vendor Research</h2>
          <p className="card-description">
            Research specific vendors using external data sources for comprehensive analysis
          </p>
        <form onSubmit={handleSubmit} className="research-form">
          <div className="form-group">
            <label htmlFor="vendor_name">Vendor Name *</label>
            <input
              type="text"
              id="vendor_name"
              name="vendor_name"
              value={formData.vendor_name}
              onChange={handleInputChange}
              placeholder="Enter vendor name (e.g., Microsoft, IBM, Accenture)"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="location">Location *</label>
            <input
              type="text"
              id="location"
              name="location"
              value={formData.location}
              onChange={handleInputChange}
              placeholder="Enter location (e.g., New York, USA, London, UK)"
              required
            />
          </div>

          <div className="external-sources-section">
            <h3>External Data Sources</h3>
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
                    name="enableRedditAnalysis"
                    checked={formData.enableRedditAnalysis}
                    onChange={handleInputChange}
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
                    name="enableLinkedInAnalysis"
                    checked={formData.enableLinkedInAnalysis}
                    onChange={handleInputChange}
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
                    name="enableGoogleReviews"
                    checked={formData.enableGoogleReviews}
                    onChange={handleInputChange}
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
            </div>
            
            {(formData.enableRedditAnalysis || formData.enableLinkedInAnalysis || formData.enableGoogleReviews) && (
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
                    formData.enableGoogleReviews && 'Google Reviews'
                  ].filter(Boolean).join(', ')
                }
              </div>
            )}
          </div>

          {error && <div className="error-message">{error}</div>}

          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1.5rem' }}>
            <button
              type="submit"
              disabled={loading}
              className="evaluate-button"
              style={{ 
                padding: '1rem 2rem',
                fontSize: '1.1rem',
                minWidth: '200px',
                height: '50px'
              }}
            >
              {loading ? (
                <>
                  <span className="spinner" style={{ marginRight: '8px' }}></span>
                  Researching...
                </>
              ) : (
                'Start Research'
              )}
            </button>
          </div>
        </form>
        </div>
      </div>

      {loading && (
        <div className="section-wrapper">
          <div
            className="card"
            style={{
              textAlign: 'center',
              padding: '2rem',
              background: 'var(--color-secondary)',
              borderRadius: '8px'
            }}
          >
          <h3>AI is researching the vendor...</h3>
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
            Please wait while the AI analyzes external data sources.<br />
            This may take 30-60 seconds depending on the data available.
          </p>
          </div>
        </div>
      )}

      {researchResult && (
        <div className="section-wrapper">
          <div className="card">
          <div className="results-header">
            <h3>Research Results for {formData.vendor_name}</h3>
            <div className="action-buttons">
              <button onClick={generatePDF} className="action-button" disabled={loading}>
                <FaFilePdf /> Generate PDF
              </button>
            </div>
          </div>

          <div id="research-results" className="research-results">
            <div className="analysis-summary">
              <h4>Analysis Summary</h4>
              <div className="summary-content">
                {researchResult?.data?.deep_analysis ? (
                  <div className="analysis-content">
                    {typeof researchResult.data.deep_analysis === 'string' ? (
                      <div dangerouslySetInnerHTML={{ __html: researchResult.data.deep_analysis.replace(/\n/g, '<br>') }} />
                    ) : (
                      <div className="analysis-json">
                        {researchResult.data.deep_analysis.overall_assessment && (
                          <div className="analysis-section">
                            <h5>Overall Assessment</h5>
                            <p>{typeof researchResult.data.deep_analysis.overall_assessment === 'string' 
                              ? researchResult.data.deep_analysis.overall_assessment 
                              : JSON.stringify(researchResult.data.deep_analysis.overall_assessment)}</p>
                          </div>
                        )}
                        
                        {formData.enableRedditAnalysis && researchResult.data.deep_analysis.reddit_insights && (
                          <div className="analysis-section">
                            <h5>💬 Reddit Community Insights</h5>
                            <p>{typeof researchResult.data.deep_analysis.reddit_insights === 'string' 
                              ? researchResult.data.deep_analysis.reddit_insights 
                              : JSON.stringify(researchResult.data.deep_analysis.reddit_insights)}</p>
                            
                            {/* Reddit Posts Links */}
                            {researchResult.data.external_data?.reddit?.mentions && researchResult.data.external_data.reddit.mentions.length > 0 && (
                              <div className="reddit-posts-section">
                                <h6>🔗 Recent Reddit Discussions</h6>
                                <div className="reddit-posts-list">
                                  {researchResult.data.external_data.reddit.mentions.slice(0, 5).map((post, index) => (
                                    <div key={index} className="reddit-post-item">
                                      <div className="reddit-post-header">
                                        <span className="reddit-subreddit">{post.subreddit}</span>
                                        <span className="reddit-engagement">
                                          {post.score} ↑ • {post.comments} 💬
                                        </span>
                                      </div>
                                      <a 
                                        href={post.url} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="reddit-post-link"
                                      >
                                        {post.title}
                                      </a>
                                      <div className="reddit-post-sentiment">
                                        <span className={`sentiment-badge ${post.sentiment}`}>
                                          {post.sentiment === 'positive' ? '😊' : post.sentiment === 'negative' ? '😞' : '😐'} {post.sentiment}  
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                {researchResult.data.external_data.reddit.mentions.length > 5 && (
                                  <p className="reddit-more-posts">
                                    +{researchResult.data.external_data.reddit.mentions.length - 5} more discussions found
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {formData.enableLinkedInAnalysis && researchResult.data.deep_analysis.linkedin_insights && (
                          <div className="analysis-section">
                            <h5>💼 LinkedIn Intelligence</h5>
                            <p>{typeof researchResult.data.deep_analysis.linkedin_insights === 'string' 
                              ? researchResult.data.deep_analysis.linkedin_insights 
                              : JSON.stringify(researchResult.data.deep_analysis.linkedin_insights)}</p>
                          </div>
                        )}
                        
                        {formData.enableGoogleReviews && researchResult.data.deep_analysis.google_reviews_insights && (
                          <div className="analysis-section">
                            <h5>⭐ Google Reviews Insights</h5>
                            {typeof researchResult.data.deep_analysis.google_reviews_insights === 'string' ? (
                              <p>{researchResult.data.deep_analysis.google_reviews_insights}</p>
                            ) : (
                              <div className="google-insights-structured">
                                {researchResult.data.deep_analysis.google_reviews_insights.overall_rating && (
                                  <div className="insight-item">
                                    <h6>📊 Overall Rating</h6>
                                    <p><strong>{researchResult.data.deep_analysis.google_reviews_insights.overall_rating}</strong> out of 5 stars ({researchResult.data.deep_analysis.google_reviews_insights.total_reviews} total reviews)</p>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.google_reviews_insights.sentiment_summary && (
                                  <div className="insight-item">
                                    <h6>😊 Sentiment Analysis</h6>
                                    <div className="sentiment-breakdown">
                                      <span className="sentiment-positive">😊 Positive: {researchResult.data.deep_analysis.google_reviews_insights.sentiment_summary.positive_reviews}</span>
                                      <span className="sentiment-negative">😞 Negative: {researchResult.data.deep_analysis.google_reviews_insights.sentiment_summary.negative_reviews}</span>
                                      <span className="sentiment-neutral">😐 Neutral: {researchResult.data.deep_analysis.google_reviews_insights.sentiment_summary.neutral_reviews}</span>
                                      <p><strong>Overall Sentiment:</strong> {researchResult.data.deep_analysis.google_reviews_insights.sentiment_summary.overall_sentiment}</p>
                                    </div>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.google_reviews_insights.review_themes && (
                                  <div className="insight-item">
                                    <h6>🎯 Key Themes</h6>
                                    {researchResult.data.deep_analysis.google_reviews_insights.review_themes.positive && researchResult.data.deep_analysis.google_reviews_insights.review_themes.positive.length > 0 && (
                                      <div className="themes-section">
                                        <h6>✅ Positive Themes</h6>
                                        <ul>
                                          {researchResult.data.deep_analysis.google_reviews_insights.review_themes.positive.map((theme, index) => (
                                            <li key={index}>{theme}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                    {researchResult.data.deep_analysis.google_reviews_insights.review_themes.negative && researchResult.data.deep_analysis.google_reviews_insights.review_themes.negative.length > 0 && (
                                      <div className="themes-section">
                                        <h6>❌ Areas for Improvement</h6>
                                        <ul>
                                          {researchResult.data.deep_analysis.google_reviews_insights.review_themes.negative.map((theme, index) => (
                                            <li key={index}>{theme}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.google_reviews_insights.latest_reviews_insights && (
                                  <div className="insight-item">
                                    <h6>📅 Recent Reviews Summary</h6>
                                    <p>{researchResult.data.deep_analysis.google_reviews_insights.latest_reviews_insights}</p>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.google_reviews_insights.additional_notes && (
                                  <div className="insight-item">
                                    <h6>📝 Additional Notes</h6>
                                    <p>{researchResult.data.deep_analysis.google_reviews_insights.additional_notes}</p>
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {/* Google Reviews Display */}
                            {researchResult.data.external_data?.google_places?.reviews && researchResult.data.external_data.google_places.reviews.length > 0 && (
                              <div className="google-reviews-section">
                                <h6>⭐ Customer Reviews ({researchResult.data.external_data.google_places.reviews.length})</h6>
                                <div className="google-reviews-summary">
                                  <div className="rating-info">
                                    <span className="overall-rating">
                                      {'★'.repeat(Math.round(researchResult.data.external_data.google_places.rating_info?.overall_rating || 0))}{'☆'.repeat(5 - Math.round(researchResult.data.external_data.google_places.rating_info?.overall_rating || 0))} {researchResult.data.external_data.google_places.rating_info?.overall_rating || 'N/A'}
                                    </span>
                                    <span className="total-reviews">
                                      ({researchResult.data.external_data.google_places.rating_info?.total_reviews || 0} total reviews)
                                    </span>
                                  </div>
                                  <div className="sentiment-info">
                                    <span className={`sentiment ${researchResult.data.external_data.google_places.sentiment_analysis?.overall_sentiment || 'neutral'}`}>
                                      {researchResult.data.external_data.google_places.sentiment_analysis?.overall_sentiment || 'neutral'} sentiment
                                    </span>
                                  </div>
                                </div>
                                
                                <div className="recent-reviews">
                                  <div className="all-reviews-link">
                                    <a 
                                      href={researchResult.data.external_data.google_places.place_id 
                                        ? `https://www.google.com/maps/place/?q=place_id:${researchResult.data.external_data.google_places.place_id}`
                                        : `https://www.google.com/maps/search/${encodeURIComponent(researchResult.data.external_data.google_places.place_info?.name || researchResult.data.vendor_name)}`
                                      }
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="all-reviews-link-btn"
                                    >
                                      📖 View All Reviews on Google Maps
                                    </a>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {researchResult.data.deep_analysis.risk_factors && researchResult.data.deep_analysis.risk_factors.length > 0 && (
                          <div className="analysis-section">
                            <h5>Risk Factors</h5>
                            <ul>
                              {researchResult.data.deep_analysis.risk_factors.map((risk, index) => (
                                <li key={index}>{risk}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {researchResult.data.deep_analysis.competitive_advantages && researchResult.data.deep_analysis.competitive_advantages.length > 0 && (
                          <div className="analysis-section">
                            <h5>Competitive Advantages</h5>
                            <ul>
                              {researchResult.data.deep_analysis.competitive_advantages.map((advantage, index) => (
                                <li key={index}>{advantage}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        
                        {researchResult.data.deep_analysis.recommendations && (
                          <div className="analysis-section">
                            <h5>💡 Recommendations</h5>
                            {typeof researchResult.data.deep_analysis.recommendations === 'string' ? (
                              <p>{researchResult.data.deep_analysis.recommendations}</p>
                            ) : (
                              <div className="recommendations-structured">
                                {researchResult.data.deep_analysis.recommendations.summary && (
                                  <div className="recommendation-item">
                                    <h6>📋 Summary</h6>
                                    <p>{researchResult.data.deep_analysis.recommendations.summary}</p>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.recommendations.key_recommendations && researchResult.data.deep_analysis.recommendations.key_recommendations.length > 0 && (
                                  <div className="recommendation-item">
                                    <h6>🎯 Key Recommendations</h6>
                                    <ul>
                                      {researchResult.data.deep_analysis.recommendations.key_recommendations.map((rec, index) => (
                                        <li key={index}>{rec}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.recommendations.considerations && researchResult.data.deep_analysis.recommendations.considerations.length > 0 && (
                                  <div className="recommendation-item">
                                    <h6>⚠️ Important Considerations</h6>
                                    <ul>
                                      {researchResult.data.deep_analysis.recommendations.considerations.map((consideration, index) => (
                                        <li key={index}>{consideration}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.recommendations.next_steps && researchResult.data.deep_analysis.recommendations.next_steps.length > 0 && (
                                  <div className="recommendation-item">
                                    <h6>🚀 Next Steps</h6>
                                    <ul>
                                      {researchResult.data.deep_analysis.recommendations.next_steps.map((step, index) => (
                                        <li key={index}>{step}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                
                                {researchResult.data.deep_analysis.recommendations.overall_assessment && (
                                  <div className="recommendation-item">
                                    <h6>📊 Overall Assessment</h6>
                                    <p>{researchResult.data.deep_analysis.recommendations.overall_assessment}</p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                        
                      </div>
                    )}
                  </div>
                ) : (
                  <p>No analysis available</p>
                )}
              </div>
            </div>


          </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default VendorResearchMode;
