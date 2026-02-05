// frontend/src/components/VendorComparisonMode.js
import React, { useState } from 'react';
import { FaPlus, FaMinus, FaSpinner, FaTable } from 'react-icons/fa';
import './VendorComparisonMode.css';
import { getJobStatus } from '../services/api';

const VendorComparisonMode = ({ workspaceName, setLoading, loading }) => {
    const [vendors, setVendors] = useState([{ name: '', location: '' }]);
    const [comparisonResults, setComparisonResults] = useState(null);
    const [error, setError] = useState('');
    const [jobId, setJobId] = useState(null);
    

    const addVendor = () => {
        setVendors([...vendors, { name: '', location: '' }]);
    };

    const removeVendor = (index) => {
        if (vendors.length > 1) {
            setVendors(vendors.filter((_, i) => i !== index));
        }
    };

    const updateVendor = (index, field, value) => {
        const updatedVendors = vendors.map((vendor, i) => 
            i === index ? { ...vendor, [field]: value } : vendor
        );
        setVendors(updatedVendors);
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

    const handleCompareVendors = async () => {
        const validVendors = vendors.filter(v => v.name.trim() && v.location.trim());
        
        if (validVendors.length < 2) {
            setError('Please add at least 2 vendors with names and locations');
            return;
        }

        setError('');
        setLoading(true);
        setComparisonResults(null);
        setJobId(null);

        try {
            const { getBackendUrl } = await import('../utils/apiUtils');
            const response = await fetch(getBackendUrl('/vendor-comparison?async_mode=true'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    vendors: validVendors,
                    workspace_name: workspaceName
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.job_id) {
                setJobId(data.job_id);
                const result = await pollJobStatus(data.job_id);
                setComparisonResults(result);
            } else {
                setComparisonResults(data);
            }
        } catch (error) {
            console.error('Error comparing vendors:', error);
            setError(`Error: ${error.message}`);
        } finally {
            setLoading(false);
            setJobId(null);
        }
    };

    return (
        <div className="vendor-comparison-mode">
            <div className="mode-header">
                <h2>Vendor Comparison</h2>
                <p>Compare multiple vendors based on AI-generated criteria</p>
            </div>

            <div className="vendor-input-section card">
                <h3>Vendors to Compare</h3>
                
                {vendors.map((vendor, index) => (
                    <div key={index} className="vendor-input-row">
                        <div className="vendor-input-group">
                            <input
                                type="text"
                                placeholder="Vendor Name (e.g., Microsoft)"
                                value={vendor.name}
                                onChange={(e) => updateVendor(index, 'name', e.target.value)}
                                className="vendor-input"
                            />
                            <input
                                type="text"
                                placeholder="Location (e.g., Redmond, WA)"
                                value={vendor.location}
                                onChange={(e) => updateVendor(index, 'location', e.target.value)}
                                className="vendor-input"
                            />
                            {vendors.length > 1 && (
                                <button 
                                    onClick={() => removeVendor(index)}
                                    className="remove-vendor-btn"
                                    title="Remove vendor"
                                >
                                    <FaMinus />
                                </button>
                            )}
                        </div>
                    </div>
                ))}

                <div className="vendor-actions">
                    <button onClick={addVendor} className="add-vendor-btn">
                        <FaPlus /> Add Vendor
                    </button>
                    <button 
                        onClick={handleCompareVendors} 
                        disabled={loading}
                        className="compare-btn"
                    >
                        {loading ? <FaSpinner className="spinner" /> : <FaTable />}
                        {loading ? 'Comparing...' : 'Compare Vendors'}
                    </button>
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
                        <h3>AI is comparing vendors...</h3>
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
                            Please wait while the AI analyzes and compares the vendors.<br />
                            This may take a moment.
                        </p>
                    </div>
                </div>
            )}

            {error && (
                <div className="error-message card">
                    <p>{error}</p>
                </div>
            )}

            {comparisonResults && !loading && (
                <div className="comparison-results">
                    <div className="results-header card">
                        <h3>Comparison Results</h3>
                        <p>AI-generated criteria and detailed vendor analysis</p>
                    </div>

                    {/* Criteria Overview */}
                    <div className="criteria-overview card">
                        <h4>Generated Criteria ({comparisonResults.criteria?.length || 0})</h4>
                        <div className="criteria-list">
                            {comparisonResults.criteria?.map((criterion, index) => (
                                <div key={index} className="criterion-item">
                                    <strong>{criterion.name}</strong>
                                    <p>{criterion.description}</p>
                                    <span className="criterion-category">{criterion.category}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Comparison Table */}
                    <div className="comparison-table-container card">
                        <h4>Detailed Comparison</h4>
                        <div className="comparison-table-wrapper">
                            <table className="comparison-table">
                                <thead>
                                    <tr>
                                        <th className="criteria-column">Criteria</th>
                                        {comparisonResults.vendors?.map((vendor, index) => (
                                            <th key={index} className="vendor-column">
                                                <div className="vendor-header">
                                                    <strong>{vendor.name}</strong>
                                                    <small>{vendor.location}</small>
                                                </div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {comparisonResults.comparison_results?.criteria_comparison?.map((criterion, index) => (
                                        <tr key={index}>
                                            <td className="criteria-cell">
                                                <div className="criterion-info">
                                                    <strong>{criterion.criterion_name}</strong>
                                                    <small>{criterion.criterion_description}</small>
                                                </div>
                                            </td>
                                            {criterion.vendor_scores?.map((vendorScore, vIndex) => (
                                                <td key={vIndex} className="vendor-cell">
                                                    <div className="vendor-score">
                                                        <div className="score-badge">
                                                            {vendorScore.score || 'N/A'}/5
                                                        </div>
                                                    </div>
                                                    <div className="vendor-rationale">
                                                        {vendorScore.rationale}
                                                    </div>
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Best Vendor Recommendation - At Bottom */}
                    {comparisonResults.comparison_results?.best_vendor && (
                        <div className="best-vendor-card card">
                            <div className="best-vendor-header">
                                <h3>🏆 Recommended Vendor</h3>
                                <div className="best-vendor-info">
                                    <h4>{comparisonResults.comparison_results.best_vendor.vendor_name}</h4>
                                </div>
                            </div>
                            <div className="best-vendor-reasoning">
                                <strong>Why this vendor:</strong>
                                <p>{comparisonResults.comparison_results.best_vendor.reasoning}</p>
                            </div>
                        </div>
                    )}

                </div>
            )}
        </div>
    );
};

export default VendorComparisonMode;
