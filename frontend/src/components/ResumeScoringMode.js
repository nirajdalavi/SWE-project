import React, { useState, useEffect } from 'react';
import { FaUpload, FaFilePdf, FaEdit, FaTrash, FaPlay, FaDownload, FaSave, FaTimes, FaEnvelope, FaSortUp, FaSortDown, FaSearch } from 'react-icons/fa';
import { uploadResume, uploadJobDescription, getResumeCriteria, updateResumeCriteria, scoreResumes, getResumeScores, saveResumeScores, getResumeFiles, getJdFiles, sendResumeEmail, getProcessingStatus, getResumeCitation, getJobStatus } from '../services/api';
import './ScoreContractsMode.css'; // Use the same CSS as ScoreContractsMode
import FileUpload from './FileUpload'; // Import FileUpload component
import CitationModal from './CitationModal'; // Import CitationModal component
import * as XLSX from 'xlsx';

const ResumeScoringMode = ({ workspaceName, setLoading, loading }) => {
    const [resumeFiles, setResumeFiles] = useState([]);
    const [jdFiles, setJdFiles] = useState([]);
    const [criteria, setCriteria] = useState([]);
    const [scoringResults, setScoringResults] = useState(null);
    const [activeTab, setActiveTab] = useState('upload');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [criteriaLoading, setCriteriaLoading] = useState(false);
    const [criteriaModified, setCriteriaModified] = useState(false);
    const [isEditing, setIsEditing] = useState(false);
    const [editableResults, setEditableResults] = useState(null);
    const [showEmailForm, setShowEmailForm] = useState(false);
    const [recipientEmail, setRecipientEmail] = useState('');
    const [emailLoading, setEmailLoading] = useState(false);
    const [sortOrder, setSortOrder] = useState('desc'); // 'asc' or 'desc'
    const [isCriteriaExtracting, setIsCriteriaExtracting] = useState(false);
    const [resumeCount, setResumeCount] = useState(0);
    const [criteriaCount, setCriteriaCount] = useState(0);
    const [topCandidatesCount, setTopCandidatesCount] = useState(3);
    const [hasUserScored, setHasUserScored] = useState(false); // Track if user has manually scored
    
    // Citation modal state
    const [citationModal, setCitationModal] = useState({
        isOpen: false,
        citation: null,
        resumeName: '',
        criterionName: '',
        rationale: ''
    });

    // Helper function to safely convert error objects to strings
    const getErrorMessage = (err) => {
        if (typeof err === 'string') return err;
        if (err?.response?.data?.detail) return String(err.response.data.detail);
        if (err?.message) return String(err.message);
        return 'An unexpected error occurred';
    };

    // Sort resumes by overall score
    const getSortedResumes = () => {
        const currentResults = isEditing ? editableResults : scoringResults;
        if (!currentResults?.resume_scores) return [];
        
        return [...currentResults.resume_scores].sort((a, b) => {
            const scoreA = parseFloat(a.overall_score) || 0;
            const scoreB = parseFloat(b.overall_score) || 0;
            
            if (sortOrder === 'desc') {
                return scoreB - scoreA; // Highest first
            } else {
                return scoreA - scoreB; // Lowest first
            }
        });
    };

    // Toggle sort order
    const toggleSortOrder = () => {
        setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc');
    };

    useEffect(() => {
        if (workspaceName) {
            fetchResumeFiles();
            fetchJdFiles();
            fetchCriteria();
            fetchScoringResults();
            
            // Check if criteria extraction is in progress
            const checkCriteriaExtraction = async () => {
                try {
                    const statusRes = await getProcessingStatus(workspaceName);
                    setIsCriteriaExtracting(statusRes.data.is_criteria_extracting);
                } catch (error) {
                    console.error('Error checking criteria extraction status:', error);
                }
            };
            checkCriteriaExtraction();
        }
    }, [workspaceName]);

    // Fetch criteria when switching to criteria tab
    useEffect(() => {
        if (activeTab === 'criteria' && workspaceName) {
            // Small delay to ensure any background processing has completed
            setTimeout(() => {
                fetchCriteria();
            }, 500);
        }
    }, [activeTab, workspaceName]);

    // Continuous polling for criteria extraction completion
    useEffect(() => {
        let pollInterval;
        
        if (isCriteriaExtracting && workspaceName) {
            pollInterval = setInterval(async () => {
                try {
                    const statusRes = await getProcessingStatus(workspaceName);
                    if (!statusRes.data.is_criteria_extracting) {
                        setIsCriteriaExtracting(false);
                        const criteriaResponse = await fetchCriteria();
                        if (criteriaResponse?.data?.criteria) {
                            setCriteriaCount(criteriaResponse.data.criteria.length);
                        }
                        setSuccess('Criteria extraction completed!');
                    }
                } catch (error) {
                    console.error('Error polling criteria extraction status:', error);
                }
            }, 3000); // Poll every 3 seconds
        }
        
        return () => {
            if (pollInterval) {
                clearInterval(pollInterval);
            }
        };
    }, [isCriteriaExtracting, workspaceName]);

    const fetchResumeFiles = async () => {
        try {
            const response = await getResumeFiles(workspaceName);
            const resumes = response.data.resumes || [];
            setResumeFiles(resumes);
            setResumeCount(resumes.length);
            return response;
        } catch (err) {
            console.error('Error fetching resume files:', err);
            // Don't set error state for fetch operations to avoid blocking UI
            return null;
        }
    };

    const fetchJdFiles = async () => {
        try {
            const response = await getJdFiles(workspaceName);
            setJdFiles(response.data.job_descriptions || []);
        } catch (err) {
            console.error('Error fetching JD files:', err);
            // Don't set error state for fetch operations to avoid blocking UI
        }
    };

    const fetchCriteria = async () => {
        try {
            console.log('Fetching criteria for workspace:', workspaceName);
            const response = await getResumeCriteria(workspaceName);
            console.log('Criteria response:', response.data);
            const criteriaData = response.data.criteria || [];
            setCriteria(criteriaData);
            setCriteriaCount(criteriaData.length);
            console.log('Criteria set to:', criteriaData);
            return response;
        } catch (err) {
            console.error('Error fetching criteria:', err);
            if (err.response?.status === 404) {
                console.log('No criteria found for workspace - this is normal for new workspaces');
                setCriteria([]);
                setCriteriaCount(0);
            } else {
                console.error('Unexpected error fetching criteria:', err.response?.data || err.message);
                // Don't set error state for fetch operations to avoid blocking UI
            }
            return null;
        }
    };

    const fetchScoringResults = async () => {
        try {
            const response = await getResumeScores(workspaceName);
            setScoringResults(response.data);
        } catch (err) {
            console.error('Error fetching scoring results:', err);
            // Don't set error state for fetch operations to avoid blocking UI
        }
    };

    const handleJdUploadSuccess = async () => {
        console.log('JD upload success handler called');
        await fetchJdFiles();
        
        // Check if criteria extraction is in progress
        try {
            const statusRes = await getProcessingStatus(workspaceName);
            const isCriteriaExtracting = statusRes.data.is_criteria_extracting;
            
            if (isCriteriaExtracting) {
                setIsCriteriaExtracting(true);
                setSuccess('Job description uploaded successfully! Extracting criteria using AI...');
            } else {
                // Criteria extraction already completed
                const response = await fetchCriteria();
                console.log('Criteria fetch response:', response?.data);
                
                // Update count immediately from response
                if (response?.data?.criteria) {
                    setCriteriaCount(response.data.criteria.length);
                    console.log('Updated criteria count to:', response.data.criteria.length);
                }
                
                setSuccess('Job description uploaded and criteria extracted successfully! (Ready for scoring)');
            }
        } catch (error) {
            console.error('Error checking processing status:', error);
            // Fallback: just fetch criteria
            const response = await fetchCriteria();
            console.log('Criteria fetch response (fallback):', response?.data);
            
            // Update count immediately from response
            if (response?.data?.criteria) {
                setCriteriaCount(response.data.criteria.length);
                console.log('Updated criteria count to:', response.data.criteria.length);
            }
            
            setSuccess('Job description uploaded successfully!');
        }
    };

    const handleResumeUploadSuccess = async () => {
        console.log('Resume upload success handler called');
        const response = await fetchResumeFiles();
        console.log('Resume fetch response:', response?.data);
        
        // Update count immediately from response
        if (response?.data?.resumes) {
            setResumeCount(response.data.resumes.length);
            console.log('Updated resume count to:', response.data.resumes.length);
        }
        
        setSuccess('Resumes uploaded and processed successfully! (Ready for scoring)');
    };

    const handleCriteriaUpdate = async (updatedCriteria) => {
        try {
            setCriteriaLoading(true);
            setError('');
            
            // Validate criteria before saving - allow empty criteria list
            if (!updatedCriteria) {
                setError('Invalid criteria data');
                return;
            }
            
            // Validate each criterion
            for (let i = 0; i < updatedCriteria.length; i++) {
                const criterion = updatedCriteria[i];
                if (!criterion.criterion || criterion.criterion.trim() === '') {
                    setError(`Criterion ${i + 1} must have a name`);
                    return;
                }
                if (!criterion.description || criterion.description.trim() === '') {
                    setError(`Criterion ${i + 1} must have a description`);
                    return;
                }
                if (!criterion.weight || criterion.weight < 1 || criterion.weight > 10) {
                    setError(`Criterion ${i + 1} must have a weight between 1 and 10`);
                    return;
                }
            }

            // Validate total weight equals 100
            const totalWeight = calculateTotalWeight(updatedCriteria);
            if (totalWeight !== 100) {
                setError(`Total weight must equal 100. Current total: ${totalWeight}`);
                return;
            }
            
            console.log('Sending criteria update:', { workspace_name: workspaceName, criteria: updatedCriteria });
            const response = await updateResumeCriteria(workspaceName, { workspace_name: workspaceName, criteria: updatedCriteria });
            console.log('Criteria update response:', response);
            setCriteria(updatedCriteria);
            setCriteriaModified(false);
            setSuccess('Criteria updated successfully! The updated criteria will be used for scoring.');
            // Refresh criteria from backend to ensure consistency
            await fetchCriteria();
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setCriteriaLoading(false);
        }
    };

    const handleScoreResumes = async () => {
        try {
            // Clear existing results and start fresh
            setScoringResults(null);
            setLoading(true); // Use parent's loading state
            setError('');
            setSuccess('Starting fresh resume scoring...');
            setHasUserScored(true); // Mark that user has manually initiated scoring
            
            console.log('Starting fresh resume scoring...');
            console.log('Loading state set to true, loading video should be visible');
            const response = await scoreResumes(workspaceName);
            console.log('Scoring response received:', response.data);
            
            // Check if we got a job_id (async mode) or direct results (sync mode)
            if (response.data.job_id) {
                console.log('Async mode: Polling for job completion, job_id:', response.data.job_id);
                await pollJobStatus(response.data.job_id);
            } else {
                // Direct results (sync mode)
                console.log('Sync mode: Direct results received:', response.data);
                setScoringResults(response.data);
                setSuccess('Resumes scored successfully!');
                setActiveTab('results');
                setLoading(false); // Turn off loading for sync mode
            }
        } catch (err) {
            setError(getErrorMessage(err));
            setLoading(false); // Turn off loading on error
        }
    };

    const pollJobStatus = async (jobId, maxAttempts = 600, pollInterval = 3000) => {
        let attempts = 0;
        
        const poll = async () => {
            try {
                attempts++;
                const response = await getJobStatus(jobId);
                const job = response.data;
                
                console.log(`Job ${jobId} status: ${job.status} (attempt ${attempts})`);
                
                if (job.status === 'SUCCESS') {
                    console.log('Job completed successfully:', job.result);
                    setScoringResults(job.result);
                    setSuccess('Resumes scored successfully!');
                    setActiveTab('results');
                    setLoading(false); // Turn off loading when job completes successfully
                    return;
                } else if (job.status === 'FAILURE') {
                    console.error('Job failed:', job.error);
                    setError(`Scoring failed: ${job.error || 'Unknown error'}`);
                    setLoading(false); // Turn off loading when job fails
                    return;
                }
                
                // Continue polling if job is still in progress
                if (attempts < maxAttempts) {
                    setTimeout(poll, pollInterval);
                } else {
                    setError('Scoring timeout - please try again');
                    setLoading(false); // Turn off loading on timeout
                }
            } catch (error) {
                console.error('Error polling job status:', error);
                setError(`Error checking scoring status: ${error.message}`);
                setLoading(false); // Turn off loading on error
            }
        };
        
        // Start polling
        poll();
    };

    // Calculate total weight of all criteria
    const calculateTotalWeight = (criteriaList) => {
        return criteriaList.reduce((total, criterion) => total + (criterion.weight || 0), 0);
    };

    // Check if weights sum to 100
    const isWeightValid = (criteriaList) => {
        return calculateTotalWeight(criteriaList) === 100;
    };

    const updateCriterionWeight = (index, newWeight) => {
        const updatedCriteria = [...criteria];
        updatedCriteria[index].weight = Math.max(1, Math.min(10, newWeight));
        setCriteria(updatedCriteria);
        setCriteriaModified(true);
    };

    const removeCriterion = (index) => {
        const updatedCriteria = criteria.filter((_, i) => i !== index);
        setCriteria(updatedCriteria);
        setCriteriaModified(true);
    };

    const addCriterion = () => {
        const newCriterion = {
            criterion: `New Criterion ${criteria.length + 1}`,
            description: 'Description for new criterion',
            weight: 10
        };
        const updatedCriteria = [...criteria, newCriterion];
        
        // If we have exactly 10 criteria, set each weight to 10
        if (updatedCriteria.length === 10) {
            updatedCriteria.forEach(criterion => {
                criterion.weight = 10;
            });
        }
        
        setCriteria(updatedCriteria);
        setCriteriaModified(true);
    };



    const updateCriterionField = (index, field, value) => {
        const updatedCriteria = [...criteria];
        updatedCriteria[index][field] = value;
        setCriteria(updatedCriteria);
        setCriteriaModified(true);
    };

    const exportResults = () => {
        if (!scoringResults) return;
        
        // Create workbook
        const workbook = XLSX.utils.book_new();
        
        // Generate scoring data for first sheet (table format)
        const scoringData = generateScoringData(scoringResults);
        const scoringSheet = XLSX.utils.aoa_to_sheet(scoringData);
        
        // Set column widths for better readability
        const columnWidths = [
            { wch: 25 }, // Candidate Name
            { wch: 20 }, // Overall Score
            { wch: 50 }  // Overall Rationale
        ];
        
        // Add widths for criteria columns (score with weight, rationale for each criterion)
        scoringResults.resume_scores[0]?.criteria_scores.forEach(() => {
            columnWidths.push({ wch: 20 }); // Score (with weight)
            columnWidths.push({ wch: 40 }); // Rationale
        });
        
        scoringSheet['!cols'] = columnWidths;
        
        // Add scoring sheet
        XLSX.utils.book_append_sheet(workbook, scoringSheet, 'Scoring Results');
        
        // Generate summary data for second sheet
        const summaryData = generateSummaryData(scoringResults);
        const summarySheet = XLSX.utils.aoa_to_sheet(summaryData);
        summarySheet['!cols'] = [{ wch: 30 }, { wch: 20 }];
        
        // Add summary sheet
        XLSX.utils.book_append_sheet(workbook, summarySheet, 'Summary');
        
        // Export the workbook
        XLSX.writeFile(workbook, `resume_scores_${workspaceName}.xlsx`);
    };

    const generateScoringData = (results) => {
        // Create headers row
        const headers = ['Candidate Name', 'Overall Score', 'Overall Rationale'];
        results.resume_scores[0]?.criteria_scores.forEach(criterion => {
            headers.push(`${criterion.criterion} Score (Weight: ${criterion.weight})`);
            headers.push(`${criterion.criterion} Rationale`);
        });

        const rows = [headers];
        
        // Add data rows
        results.resume_scores.forEach(resume => {
            const row = [
                resume.resume_name,
                `${(resume.overall_score * 10).toFixed(1)}%`,
                resume.overall_rationale || 'No overall rationale available'
            ];
            
            results.resume_scores[0]?.criteria_scores.forEach(criterion => {
                const scoreData = resume.criteria_scores.find(s => s.criterion === criterion.criterion);
                row.push(scoreData?.score || 'N/A');
                row.push(scoreData?.rationale || 'N/A');
            });
            rows.push(row);
        });

        return rows;
    };

    const generateSummaryData = (results) => {
        const summary = results.summary;
        return [
            ['Resume Scoring Summary', ''],
            ['', ''],
            ['Total Resumes', summary.total_resumes],
            ['Average Score', `${(summary.average_score * 10).toFixed(1)}%`],
            ['Highest Score', `${(summary.highest_score * 10).toFixed(1)}%`],
            ['Lowest Score', `${(summary.lowest_score * 10).toFixed(1)}%`],
            ['Best Resume', summary.best_resume],
            ['', ''],
            ['Why Best Resume Was Selected:', ''],
            ...(summary.best_resume_bullets || []).map(bullet => ['', bullet])
        ];
    };

    // Calculate overall score for a resume based on criteria scores and weights
    const calculateOverallScore = (criteriaScores) => {
        let totalWeightedScore = 0;
        let totalWeight = 0;
        
        criteriaScores.forEach(scoreData => {
            const score = parseFloat(scoreData.score) || 0;
            const weight = parseFloat(scoreData.weight) || 0;
            totalWeightedScore += score * weight;
            totalWeight += weight;
        });
        
        return totalWeight > 0 ? totalWeightedScore / totalWeight : 0;
    };

    // Get color based on score for color coding
    const getScoreColor = (score) => {
        const numScore = parseFloat(score) || 0;
        
        if (numScore >= 9 && numScore <= 10) {
            return {
                backgroundColor: '#d1f2d1',
                color: '#0f5132',
                border: '1px solid #badbcc'
            };
        } else if (numScore >= 7 && numScore <= 9) {
            return {
                backgroundColor: '#cce7ff',
                color: '#084298',
                border: '1px solid #b6d4fe'
            };
        } else if (numScore >= 5 && numScore <= 7) {
            return {
                backgroundColor: '#fff3cd',
                color: '#664d03',
                border: '1px solid #ffecb5'
            };
        } else if (numScore >= 1 && numScore <= 5) {
            return {
                backgroundColor: '#f8d7da',
                color: '#721c24',
                border: '1px solid #f5c2c7'
            };
        } else {
            // Default case for scores outside the range
            return {
                backgroundColor: '#f8d7da',
                color: '#721c24',
                border: '1px solid #f5c2c7'
            };
        }
    };

    // Calculate summary statistics from editable results
    const calculateSummaryStats = (results) => {
        if (!results || !results.resume_scores) return null;
        
        let totalScore = 0;
        let bestScore = 0;
        let worstScore = 10;
        let bestResume = '';
        let worstResume = '';
        
        results.resume_scores.forEach(resume => {
            const overallScore = calculateOverallScore(resume.criteria_scores);
            totalScore += overallScore;
            
            if (overallScore > bestScore) {
                bestScore = overallScore;
                bestResume = resume.resume_name;
            }
            if (overallScore < worstScore) {
                worstScore = overallScore;
                worstResume = resume.resume_name;
            }
        });
        
        // Note: AI-powered summary bullets are now generated in the backend
        // and included in the scoring results
        const bestResumeBullets = results.summary?.best_resume_bullets || [];
        
        return {
            total_resumes: results.resume_scores.length,
            average_score: totalScore / results.resume_scores.length,
            highest_score: bestScore,
            lowest_score: worstScore,
            best_resume: bestResume,
            worst_resume: worstResume,
            best_resume_bullets: bestResumeBullets
        };
    };

    const handleEditMode = () => {
        setEditableResults(JSON.parse(JSON.stringify(scoringResults))); // Deep copy
        setIsEditing(true);
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
        setEditableResults(null);
    };

    const handleSaveEdit = async () => {
        try {
            setError('');
            // Save to backend
            await saveResumeScores(workspaceName, {
                resume_scores: editableResults.resume_scores,
                summary: editableResults.summary
            });
            
            // Update local state
            setScoringResults(editableResults);
            setIsEditing(false);
            setEditableResults(null);
            setSuccess('Scoring results saved successfully!');
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const handleScoreChange = (resumeName, criterionName, newScore) => {
        if (!editableResults) return;
        
        const updatedResults = JSON.parse(JSON.stringify(editableResults));
        const resume = updatedResults.resume_scores.find(r => r.resume_name === resumeName);
        const criterionScore = resume?.criteria_scores.find(s => s.criterion === criterionName);
        
        if (criterionScore) {
            criterionScore.score = Math.max(1, Math.min(10, parseFloat(newScore) || 0));
            // Recalculate overall score
            resume.overall_score = calculateOverallScore(resume.criteria_scores);
        }
        
        // Recalculate summary statistics
        updatedResults.summary = calculateSummaryStats(updatedResults);
        setEditableResults(updatedResults);
    };

    const handleRationaleChange = (resumeName, criterionName, newRationale) => {
        if (!editableResults) return;
        
        const updatedResults = JSON.parse(JSON.stringify(editableResults));
        const resume = updatedResults.resume_scores.find(r => r.resume_name === resumeName);
        const criterionScore = resume?.criteria_scores.find(s => s.criterion === criterionName);
        
        if (criterionScore) {
            criterionScore.rationale = newRationale;
        }
        
        setEditableResults(updatedResults);
    };

    const handleSendEmail = async () => {
        try {
            setEmailLoading(true);
            setError('');
            
            if (!recipientEmail.trim()) {
                setError('Please enter a recipient email address');
                return;
            }
            
            const emailData = {
                recipient_email: recipientEmail,
                subject: 'Resume Scoring Results',
                message: 'Please find attached the resume scoring results.'
            };
            
            await sendResumeEmail(workspaceName, emailData);
            setSuccess('Email sent successfully!');
            setShowEmailForm(false);
            setRecipientEmail('');
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setEmailLoading(false);
        }
    };

    const handleCitationClick = async (resumeName, criterionName, rationale) => {
        try {
            setError('');
            const response = await getResumeCitation(workspaceName, resumeName, criterionName);
            
            setCitationModal({
                isOpen: true,
                citation: response.data,
                resumeName: resumeName,
                criterionName: criterionName,
                rationale: rationale
            });
        } catch (err) {
            setError(getErrorMessage(err));
        }
    };

    const closeCitationModal = () => {
        setCitationModal({
            isOpen: false,
            citation: null,
            resumeName: '',
            criterionName: '',
            rationale: ''
        });
    };

    return (
        <div className="score-contracts-mode">
            <div className="section-wrapper">
                <div className="card">
                    <h3 className="card-title">Resume Scoring Mode</h3>
                    <p className="small-text">Upload job descriptions, extract criteria, and score resumes against them</p>
                </div>
            </div>

            {error && (
                <div className="section-wrapper">
                    <p className="error-message">Error: {error}</p>
                </div>
            )}
            
            {success && (
                <div className="section-wrapper">
                    <p className="success-message">{success}</p>
                </div>
            )}

            {/* Tab Navigation */}
            <div className="section-wrapper">
                <div style={{ 
                    backgroundColor: 'var(--color-secondary)', 
                    padding: '0', 
                    marginBottom: '2rem',
                    borderRadius: '8px 8px 0 0',
                    overflow: 'hidden'
                }}>
                    <div style={{ display: 'flex', width: '100%' }}>
                        <button 
                            onClick={() => setActiveTab('upload')}
                            style={{ 
                                flex: 1,
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                gap: '0.5rem',
                                padding: '1rem',
                                backgroundColor: activeTab === 'upload' ? 'var(--color-primary)' : 'transparent',
                                color: activeTab === 'upload' ? 'white' : 'var(--color-muted)',
                                border: 'none',
                                borderBottom: 'none',
                                borderTop: 'none',
                                borderLeft: 'none',
                                borderRight: 'none',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: activeTab === 'upload' ? '8px' : '0',
                                boxShadow: activeTab === 'upload' ? '0 2px 8px rgba(0, 0, 0, 0.2)' : 'none',
                                margin: activeTab === 'upload' ? '4px' : '0',
                                marginBottom: activeTab === 'upload' ? '0' : '4px'
                            }}
                        >
                            <FaUpload /> Upload Files
                        </button>
                        <button 
                            onClick={() => setActiveTab('criteria')}
                            style={{ 
                                flex: 1,
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                gap: '0.5rem',
                                padding: '1rem',
                                backgroundColor: activeTab === 'criteria' ? 'var(--color-primary)' : 'transparent',
                                color: activeTab === 'criteria' ? 'white' : 'var(--color-muted)',
                                border: 'none',
                                borderBottom: 'none',
                                borderTop: 'none',
                                borderLeft: 'none',
                                borderRight: 'none',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: activeTab === 'criteria' ? '8px' : '0',
                                boxShadow: activeTab === 'criteria' ? '0 2px 8px rgba(0, 0, 0, 0.2)' : 'none',
                                margin: activeTab === 'criteria' ? '4px' : '0',
                                marginBottom: activeTab === 'criteria' ? '0' : '4px'
                            }}
                        >
                            <FaEdit /> Manage Criteria
                        </button>
                        <button 
                            onClick={() => setActiveTab('results')}
                            style={{ 
                                flex: 1,
                                display: 'flex', 
                                alignItems: 'center', 
                                justifyContent: 'center',
                                gap: '0.5rem',
                                padding: '1rem',
                                backgroundColor: activeTab === 'results' ? 'var(--color-primary)' : 'transparent',
                                color: activeTab === 'results' ? 'white' : 'var(--color-muted)',
                                border: 'none',
                                borderBottom: 'none',
                                borderTop: 'none',
                                borderLeft: 'none',
                                borderRight: 'none',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                borderRadius: activeTab === 'results' ? '8px' : '0',
                                boxShadow: activeTab === 'results' ? '0 2px 8px rgba(0, 0, 0, 0.2)' : 'none',
                                margin: activeTab === 'results' ? '4px' : '0',
                                marginBottom: activeTab === 'results' ? '0' : '4px'
                            }}
                        >
                            <FaPlay /> Scoring Results
                        </button>
                    </div>
                </div>
            </div>

            {/* Loading Video for Resume Scoring */}
            {loading && (
                <div className="section-wrapper">
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
                        <h3>AI is scoring resumes...</h3>
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
                            Please wait while the AI evaluates resumes against the criteria.<br />
                            This may take a moment.
                        </p>
                    </div>
                </div>
            )}

            {/* Upload Tab */}
            {activeTab === 'upload' && (
                <div className="section-wrapper">
                    <div className="card">
                        <h3 className="card-title">Upload Files</h3>
                        <div className="file-upload-sections-container">
                            <div className="file-upload-card">
                                <FileUpload
                                    workspaceName={workspaceName}
                                    fileType="job_description"
                                    onUploadSuccess={handleJdUploadSuccess}
                                />
                            </div>
                            <div className="file-upload-card">
                                <FileUpload
                                    workspaceName={workspaceName}
                                    fileType="resumes"
                                    onUploadSuccess={handleResumeUploadSuccess}
                                />
                            </div>
                        </div>

                        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
                            <div className="card" style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'left' }}>
                                <h4>Ready to Score</h4>
                                <p>✅ {resumeCount} resume(s) uploaded and processed</p>
                                <p>✅ {criteriaCount} criteria extracted from job description</p>
                                <p>🚀 Ready to score resumes against criteria</p>
                                <button 
                                    className="evaluate-button"
                                    onClick={handleScoreResumes}
                                    disabled={loading || resumeCount === 0 || criteriaCount === 0}
                                    style={{ marginTop: '1rem' }}
                                >
                                    {loading ? 'AI is scoring resumes...' : '🎯 Score Resumes Now'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Criteria Tab */}
            {activeTab === 'criteria' && (
                <div className="section-wrapper">
                    <div className="card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h3 className="card-title">Scoring Criteria</h3>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <div style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: '0.5rem',
                                    padding: '0.5rem 1rem',
                                    backgroundColor: isWeightValid(criteria) ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
                                    color: isWeightValid(criteria) ? 'var(--color-success)' : 'var(--color-error)',
                                    borderRadius: '6px',
                                    fontSize: '0.9rem',
                                    fontWeight: '500'
                                }}>
                                    <span>Total Weight: {calculateTotalWeight(criteria)}/100</span>
                                    {isWeightValid(criteria) ? '✅' : '❌'}
                                </div>
                                <button className="button" onClick={addCriterion}>
                                    Add Criterion
                                </button>
                            </div>
                        </div>

                        {isCriteriaExtracting && (
                            <div className="card" style={{ textAlign: 'center', padding: '2rem', background: 'var(--color-secondary)', borderRadius: '8px' }}>
                                <h4>Extracting Criteria...</h4>
                                <video
                                    src="/ai-thinking.mp4"
                                    className="loading-icon"
                                    autoPlay
                                    loop
                                    muted
                                    playsInline
                                    style={{ maxWidth: '300px', margin: '1rem auto' }}
                                />
                                <p style={{ marginTop: '1rem', color: '#666' }}>
                                    AI is analyzing the job description to extract relevant criteria.
                                    This may take a moment.
                                </p>
                            </div>
                        )}

                        {!isCriteriaExtracting && criteria.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '2rem', background: 'var(--color-secondary)', borderRadius: '8px' }}>
                                <p>No criteria defined. You can save an empty criteria list or add criteria to evaluate resumes.</p>
                                <p className="small-text" style={{ color: 'var(--color-primary)', fontStyle: 'italic' }}>
                                    💡 Tip: Upload a job description to automatically generate criteria, or add them manually.
                                </p>
                            </div>
                        ) : !isCriteriaExtracting && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {criteria.map((criterion, index) => (
                                    <div key={index} className="card" style={{ padding: '1.5rem' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                            <input
                                                type="text"
                                                value={criterion.criterion}
                                                onChange={(e) => updateCriterionField(index, 'criterion', e.target.value)}
                                                className="input-field"
                                                placeholder="Criterion name"
                                                style={{ flex: 1, marginRight: '1rem', padding: '0.75rem 1.2rem', fontSize: '1rem', border: '2px solid #d1d5db', borderRadius: '12px', backgroundColor: '#f9fafb' }}
                                            />
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                <input
                                                    type="number"
                                                    min="1"
                                                    max="10"
                                                    value={criterion.weight}
                                                    onChange={(e) => updateCriterionWeight(index, parseInt(e.target.value))}
                                                    className="score-input"
                                                    style={{ width: '80px' }}
                                                />
                                                <button 
                                                    className="button secondary"
                                                    onClick={() => removeCriterion(index)}
                                                    style={{ padding: '0.5rem' }}
                                                >
                                                    <FaTrash />
                                                </button>
                                            </div>
                                        </div>
                                        <textarea
                                            value={criterion.description}
                                            onChange={(e) => updateCriterionField(index, 'description', e.target.value)}
                                            className="input-field"
                                            placeholder="Description of what this criterion evaluates"
                                            rows={3}
                                        />
                                    </div>
                                ))}
                            </div>
                        )}

                        {!isWeightValid(criteria) && criteria.length > 0 && (
                            <div style={{ 
                                marginTop: '1.5rem', 
                                padding: '1rem', 
                                backgroundColor: 'var(--color-error-bg)', 
                                border: '1px solid var(--color-error)',
                                borderRadius: '8px',
                                color: 'var(--color-error)',
                                textAlign: 'center'
                            }}>
                                <strong>⚠️ Weight Validation Error:</strong> The total weight of all criteria must equal 100. 
                                Current total: {calculateTotalWeight(criteria)}. 
                                Please adjust the weights so they sum to exactly 100.
                            </div>
                        )}

                        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
                            <button 
                                className={`button ${criteriaModified ? 'active' : 'secondary'}`}
                                onClick={() => handleCriteriaUpdate(criteria)}
                                disabled={criteriaLoading || isCriteriaExtracting || !isWeightValid(criteria)}
                            >
                                {criteriaLoading ? 'Saving...' : criteriaModified ? '💾 Save Changes' : 'Save Criteria'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Results Tab */}
            {activeTab === 'results' && (
                <div className="section-wrapper">
                    <div className="card">
                        {!scoringResults || !scoringResults.resume_scores || scoringResults.resume_scores.length === 0 ? (
                            <p>No scoring results found. Please score resumes first.</p>
                        ) : (
                            <>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                                    <div>
                                        <h3 className="card-title">Scoring Results</h3>
                                        <p style={{ 
                                            margin: '8px 0 0 0', 
                                            color: '#6c757d', 
                                            fontSize: '14px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '6px'
                                        }}>
                                            <FaSearch style={{ fontSize: '12px' }} />
                                            Click on any cell to view citation and source document
                                        </p>
                                    </div>
                                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                                        {!isEditing ? (
                                            <button 
                                                style={{
                                                    padding: '10px 16px',
                                                    backgroundColor: 'white',
                                                    color: '#495057',
                                                    border: '1px solid #dee2e6',
                                                    borderRadius: '6px',
                                                    fontWeight: '500',
                                                    fontSize: '14px',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '6px',
                                                    transition: 'all 0.2s ease'
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.target.style.backgroundColor = '#f8f9fa';
                                                    e.target.style.borderColor = '#adb5bd';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.target.style.backgroundColor = 'white';
                                                    e.target.style.borderColor = '#dee2e6';
                                                }}
                                                onClick={handleEditMode}
                                            >
                                                <FaEdit /> Edit Results
                                            </button>
                                        ) : (
                                            <>
                                                <button 
                                                    style={{
                                                        padding: '10px 16px',
                                                        backgroundColor: 'white',
                                                        color: '#495057',
                                                        border: '1px solid #dee2e6',
                                                        borderRadius: '6px',
                                                        fontWeight: '500',
                                                        fontSize: '14px',
                                                        cursor: 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '6px',
                                                        transition: 'all 0.2s ease'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        e.target.style.backgroundColor = '#f8f9fa';
                                                        e.target.style.borderColor = '#adb5bd';
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        e.target.style.backgroundColor = 'white';
                                                        e.target.style.borderColor = '#dee2e6';
                                                    }}
                                                    onClick={handleSaveEdit}
                                                >
                                                    <FaSave /> Save Changes
                                                </button>
                                                <button 
                                                    style={{
                                                        padding: '10px 16px',
                                                        backgroundColor: 'white',
                                                        color: '#495057',
                                                        border: '1px solid #dee2e6',
                                                        borderRadius: '6px',
                                                        fontWeight: '500',
                                                        fontSize: '14px',
                                                        cursor: 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '6px',
                                                        transition: 'all 0.2s ease'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        e.target.style.backgroundColor = '#f8f9fa';
                                                        e.target.style.borderColor = '#adb5bd';
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        e.target.style.backgroundColor = 'white';
                                                        e.target.style.borderColor = '#dee2e6';
                                                    }}
                                                    onClick={handleCancelEdit}
                                                >
                                                    <FaTimes /> Cancel
                                                </button>
                                            </>
                                        )}
                                        <button 
                                            style={{
                                                padding: '10px 16px',
                                                backgroundColor: 'white',
                                                color: '#495057',
                                                border: '1px solid #dee2e6',
                                                borderRadius: '6px',
                                                fontWeight: '500',
                                                fontSize: '14px',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px',
                                                transition: 'all 0.2s ease'
                                            }}
                                            onMouseEnter={(e) => {
                                                e.target.style.backgroundColor = '#f8f9fa';
                                                e.target.style.borderColor = '#adb5bd';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.target.style.backgroundColor = 'white';
                                                e.target.style.borderColor = '#dee2e6';
                                            }}
                                            onClick={exportResults}
                                        >
                                            <FaDownload /> Export Results
                                        </button>
                                        <button 
                                            style={{
                                                padding: '10px 16px',
                                                backgroundColor: '#0d6efd',
                                                color: 'white',
                                                border: '1px solid #0d6efd',
                                                borderRadius: '6px',
                                                fontWeight: '500',
                                                fontSize: '14px',
                                                cursor: 'pointer',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px',
                                                transition: 'all 0.2s ease'
                                            }}
                                            onMouseEnter={(e) => {
                                                e.target.style.backgroundColor = '#0b5ed7';
                                                e.target.style.borderColor = '#0b5ed7';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.target.style.backgroundColor = '#0d6efd';
                                                e.target.style.borderColor = '#0d6efd';
                                            }}
                                            onClick={() => setShowEmailForm(!showEmailForm)}
                                        >
                                            <FaEnvelope /> Send Email
                                        </button>
                                    </div>
                                </div>

                                {/* Email Form */}
                                {showEmailForm && (
                                    <div className="card" style={{ marginBottom: '1.5rem' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                            <h4>Send Results via Email</h4>
                                            <button 
                                                style={{
                                                    padding: '8px 12px',
                                                    backgroundColor: 'white',
                                                    color: '#495057',
                                                    border: '1px solid #dee2e6',
                                                    borderRadius: '6px',
                                                    fontWeight: '500',
                                                    fontSize: '14px',
                                                    cursor: 'pointer',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '6px',
                                                    transition: 'all 0.2s ease'
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.target.style.backgroundColor = '#f8f9fa';
                                                    e.target.style.borderColor = '#adb5bd';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.target.style.backgroundColor = 'white';
                                                    e.target.style.borderColor = '#dee2e6';
                                                }}
                                                onClick={() => setShowEmailForm(false)}
                                            >
                                                <FaTimes />
                                            </button>
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                            <div>
                                                <label className="small-text">Recipient Email:</label>
                                                <input
                                                    type="email"
                                                    value={recipientEmail}
                                                    onChange={(e) => setRecipientEmail(e.target.value)}
                                                    placeholder="Enter recipient email address"
                                                    disabled={emailLoading}
                                                    className="input-field"
                                                />
                                            </div>
                                            <div style={{ display: 'flex', gap: '0.75rem' }}>
                                                <button 
                                                    style={{
                                                        padding: '10px 16px',
                                                        backgroundColor: '#0d6efd',
                                                        color: 'white',
                                                        border: '1px solid #0d6efd',
                                                        borderRadius: '6px',
                                                        fontWeight: '500',
                                                        fontSize: '14px',
                                                        cursor: emailLoading || !recipientEmail.trim() ? 'not-allowed' : 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '6px',
                                                        transition: 'all 0.2s ease',
                                                        opacity: emailLoading || !recipientEmail.trim() ? '0.6' : '1'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        if (!emailLoading && recipientEmail.trim()) {
                                                            e.target.style.backgroundColor = '#0b5ed7';
                                                            e.target.style.borderColor = '#0b5ed7';
                                                        }
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        if (!emailLoading && recipientEmail.trim()) {
                                                            e.target.style.backgroundColor = '#0d6efd';
                                                            e.target.style.borderColor = '#0d6efd';
                                                        }
                                                    }}
                                                    onClick={handleSendEmail}
                                                    disabled={emailLoading || !recipientEmail.trim()}
                                                >
                                                    {emailLoading ? 'Sending...' : 'Send Email'}
                                                </button>
                                                <button 
                                                    style={{
                                                        padding: '10px 16px',
                                                        backgroundColor: 'white',
                                                        color: '#495057',
                                                        border: '1px solid #dee2e6',
                                                        borderRadius: '6px',
                                                        fontWeight: '500',
                                                        fontSize: '14px',
                                                        cursor: emailLoading ? 'not-allowed' : 'pointer',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '6px',
                                                        transition: 'all 0.2s ease',
                                                        opacity: emailLoading ? '0.6' : '1'
                                                    }}
                                                    onMouseEnter={(e) => {
                                                        if (!emailLoading) {
                                                            e.target.style.backgroundColor = '#f8f9fa';
                                                            e.target.style.borderColor = '#adb5bd';
                                                        }
                                                    }}
                                                    onMouseLeave={(e) => {
                                                        if (!emailLoading) {
                                                            e.target.style.backgroundColor = 'white';
                                                            e.target.style.borderColor = '#dee2e6';
                                                        }
                                                    }}
                                                    onClick={() => setShowEmailForm(false)}
                                                    disabled={emailLoading}
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                            <div style={{ background: 'var(--color-secondary)', padding: '0.75rem', borderRadius: '6px' }}>
                                                <p className="small-text" style={{ margin: 0, color: 'var(--color-primary)' }}>
                                                    📎 Excel file with scoring results will be automatically attached
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                <div className="scoring-matrix-scroll-wrapper">
                                    <table className="scoring-matrix-table" style={{ 
                                        minWidth: '1200px',
                                        borderCollapse: 'separate',
                                        borderSpacing: '8px',
                                        width: '100%'
                                    }}>
                                        <thead>
                                            <tr>
                                                <th style={{ 
                                                    padding: '16px', 
                                                    textAlign: 'left', 
                                                    backgroundColor: '#f8f9fa', 
                                                    border: '1px solid #e9ecef',
                                                    borderRadius: '8px',
                                                    fontWeight: 'bold',
                                                    fontSize: '16px',
                                                    color: '#495057'
                                                }}>Candidate</th>
                                                {(isEditing ? editableResults : scoringResults).resume_scores[0]?.criteria_scores.map((criterion, index) => (
                                                    <th key={index} style={{ 
                                                        padding: '16px', 
                                                        textAlign: 'center', 
                                                        backgroundColor: '#f8f9fa', 
                                                        border: '1px solid #e9ecef',
                                                        borderRadius: '8px',
                                                        fontWeight: 'bold',
                                                        fontSize: '16px',
                                                        color: '#495057'
                                                    }}>
                                                        <div style={{ fontWeight: 'bold', fontSize: '16px', marginBottom: '4px' }}>{criterion.criterion}</div>
                                                        <div style={{ fontSize: '14px', opacity: '0.8', color: '#6c757d' }}>
                                                            Weight: {criterion.weight}
                                                        </div>
                                                    </th>
                                                ))}
                                                                                                                                                        <th 
                                                        style={{ 
                                                            padding: '16px', 
                                                            textAlign: 'center', 
                                                            backgroundColor: '#f8f9fa', 
                                                            border: '1px solid #e9ecef',
                                                            borderRadius: '8px',
                                                            cursor: 'pointer',
                                                            fontWeight: 'bold',
                                                            fontSize: '14px',
                                                            color: '#495057'
                                                        }}
                                                        onClick={toggleSortOrder}
                                                    >
                                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontWeight: 'bold', fontSize: '16px' }}>
                                                            Overall Score
                                                            {sortOrder === 'desc' ? <FaSortDown /> : <FaSortUp />}
                                                        </div>
                                                    </th>
                                                    <th style={{ 
                                                        padding: '16px', 
                                                        textAlign: 'center', 
                                                        backgroundColor: '#f8f9fa', 
                                                        border: '1px solid #e9ecef',
                                                        borderRadius: '8px',
                                                        fontWeight: 'bold',
                                                        fontSize: '16px',
                                                        color: '#495057'
                                                    }}>
                                                        <div style={{ fontWeight: 'bold', fontSize: '16px' }}>Overall Rationale</div>
                                                    </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {getSortedResumes().map((resume, resumeIndex) => (
                                                <tr key={resumeIndex}>
                                                    <td style={{ 
                                                        padding: '16px', 
                                                        fontWeight: 'bold', 
                                                        fontSize: '16px',
                                                        backgroundColor: '#f8f9fa',
                                                        border: '1px solid #e9ecef',
                                                        borderRadius: '8px',
                                                        minWidth: '200px',
                                                        width: '200px',
                                                        color: '#495057'
                                                    }}>
                                                        {resume.resume_name}
                                                    </td>
                                                    {(isEditing ? editableResults : scoringResults).resume_scores[0]?.criteria_scores.map((criterion, criterionIndex) => {
                                                        const criterionScore = resume.criteria_scores.find(
                                                            score => score.criterion === criterion.criterion
                                                        );
                                                        const criterionData = criteria.find(c => c.criterion === criterion.criterion);
                                                        const weight = criterionData?.weight || 0;
                                                        const weightedScore = criterionScore?.score ? ((criterionScore.score * weight) / 10).toFixed(1) : 'N/A';
                                                        const scoreColor = getScoreColor(criterionScore?.score);
                                                        return (
                                                            <td key={criterionIndex} style={{
                                                                padding: '16px',
                                                                backgroundColor: scoreColor.backgroundColor,
                                                                border: scoreColor.border,
                                                                borderRadius: '8px',
                                                                minHeight: '80px',
                                                                minWidth: '250px',
                                                                width: '250px',
                                                                verticalAlign: 'top',
                                                                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                                                                cursor: isEditing ? 'default' : 'pointer',
                                                                position: 'relative'
                                                            }}
                                                            onClick={isEditing ? undefined : () => handleCitationClick(
                                                                resume.resume_name, 
                                                                criterion.criterion, 
                                                                criterionScore?.rationale || ''
                                                            )}
                                                            onMouseEnter={isEditing ? undefined : (e) => {
                                                                e.target.style.transform = 'scale(1.02)';
                                                                e.target.style.transition = 'transform 0.2s ease';
                                                            }}
                                                            onMouseLeave={isEditing ? undefined : (e) => {
                                                                e.target.style.transform = 'scale(1)';
                                                            }}
                                                            >
                                                                {isEditing ? (
                                                                    <div style={{ 
                                                                        display: 'flex', 
                                                                        flexDirection: 'column', 
                                                                        justifyContent: 'center', 
                                                                        alignItems: 'center',
                                                                        height: '100%',
                                                                        gap: '8px'
                                                                    }}>
                                                                        <input
                                                                            type="number"
                                                                            min="1"
                                                                            max="10"
                                                                            step="0.1"
                                                                            value={criterionScore?.score || ''}
                                                                            onChange={(e) => handleScoreChange(resume.resume_name, criterion.criterion, e.target.value)}
                                                                            className="score-input"
                                                                            style={{ 
                                                                                width: '50px',
                                                                                height: '40px',
                                                                                textAlign: 'center',
                                                                                fontWeight: 'bold',
                                                                                fontSize: '16px',
                                                                                backgroundColor: 'white',
                                                                                border: '2px solid #e9ecef',
                                                                                borderRadius: '8px',
                                                                                color: '#495057',
                                                                                outline: 'none',
                                                                                transition: 'border-color 0.2s ease'
                                                                            }}
                                                                            onFocus={(e) => {
                                                                                e.target.style.borderColor = '#0d6efd';
                                                                            }}
                                                                            onBlur={(e) => {
                                                                                e.target.style.borderColor = '#e9ecef';
                                                                            }}
                                                                        />
                                                                        <textarea
                                                                            value={criterionScore?.rationale || ''}
                                                                            onChange={(e) => handleRationaleChange(resume.resume_name, criterion.criterion, e.target.value)}
                                                                            className="input-field"
                                                                            style={{ 
                                                                                width: '100%', 
                                                                                height: '60px', 
                                                                                fontSize: '13px', 
                                                                                lineHeight: '1.4',
                                                                                resize: 'none',
                                                                                backgroundColor: 'white',
                                                                                border: '2px solid #e9ecef',
                                                                                borderRadius: '8px',
                                                                                padding: '12px',
                                                                                color: '#495057',
                                                                                outline: 'none',
                                                                                fontFamily: 'inherit',
                                                                                transition: 'border-color 0.2s ease'
                                                                            }}
                                                                            onFocus={(e) => {
                                                                                e.target.style.borderColor = '#0d6efd';
                                                                            }}
                                                                            onBlur={(e) => {
                                                                                e.target.style.borderColor = '#e9ecef';
                                                                            }}
                                                                            placeholder="Enter description..."
                                                                        />
                                                                    </div>
                                                                ) : (
                                                                    <div>
                                                                        <div style={{ 
                                                                            textAlign: 'center', 
                                                                            marginBottom: '8px',
                                                                            fontWeight: 'bold',
                                                                            fontSize: '16px',
                                                                            color: scoreColor.color
                                                                        }}>
                                                                            {weightedScore}
                                                                        </div>
                                                                        <div style={{
                                                                            color: scoreColor.color,
                                                                            fontSize: '15px',
                                                                            lineHeight: '1.4',
                                                                            fontWeight: '500'
                                                                        }}>
                                                                            {criterionScore?.rationale || 'No description available'}
                                                                        </div>
                                                                        <div style={{
                                                                            position: 'absolute',
                                                                            top: '8px',
                                                                            right: '8px',
                                                                            color: scoreColor.color,
                                                                            opacity: '0.7',
                                                                            fontSize: '12px'
                                                                        }}>
                                                                            <FaSearch />
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </td>
                                                        );
                                                    })}
                                                    <td style={{ 
                                                        textAlign: 'center', 
                                                        fontWeight: 'bold', 
                                                        fontSize: '18px',
                                                        padding: '16px',
                                                        backgroundColor: '#f8f9fa',
                                                        border: '1px solid #e9ecef',
                                                        borderRadius: '8px',
                                                        minWidth: '120px',
                                                        width: '120px',
                                                        color: '#495057'
                                                    }}>
                                                        {(resume.overall_score * 10).toFixed(1)}%
                                                    </td>
                                                    <td style={{ 
                                                        fontSize: '14px', 
                                                        color: '#6c757d', 
                                                        lineHeight: '1.3', 
                                                        width: '350px', 
                                                        minWidth: '350px', 
                                                        padding: '16px',
                                                        backgroundColor: '#f8f9fa',
                                                        border: '1px solid #e9ecef',
                                                        borderRadius: '8px'
                                                    }}>
                                                        {resume.overall_rationale || 'No overall rationale available'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>

                                {/* Color Coding Legend */}
                                <div style={{ 
                                    display: 'flex', 
                                    justifyContent: 'center', 
                                    gap: '1rem', 
                                    marginTop: '1.5rem',
                                    flexWrap: 'wrap'
                                }}>
                                    <div style={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        gap: '0.5rem',
                                        padding: '0.75rem 1rem',
                                        backgroundColor: 'var(--color-card)',
                                        color: 'var(--color-text)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '6px',
                                        fontWeight: 'bold',
                                        fontSize: '14px'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            backgroundColor: '#d1f2d1',
                                            border: '1px solid #badbcc',
                                            borderRadius: '3px'
                                        }}></div>
                                        90-100%: Excellent
                                    </div>
                                    <div style={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        gap: '0.5rem',
                                        padding: '0.75rem 1rem',
                                        backgroundColor: 'var(--color-card)',
                                        color: 'var(--color-text)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '6px',
                                        fontWeight: 'bold',
                                        fontSize: '14px'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            backgroundColor: '#cce7ff',
                                            border: '1px solid #b6d4fe',
                                            borderRadius: '3px'
                                        }}></div>
                                        70-90%: Good
                                    </div>
                                    <div style={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        gap: '0.5rem',
                                        padding: '0.75rem 1rem',
                                        backgroundColor: 'var(--color-card)',
                                        color: 'var(--color-text)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '6px',
                                        fontWeight: 'bold',
                                        fontSize: '14px'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            backgroundColor: '#fff3cd',
                                            border: '1px solid #ffecb5',
                                            borderRadius: '3px'
                                        }}></div>
                                        50-70%: Average
                                    </div>
                                    <div style={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        gap: '0.5rem',
                                        padding: '0.75rem 1rem',
                                        backgroundColor: 'var(--color-card)',
                                        color: 'var(--color-text)',
                                        border: '1px solid var(--color-border)',
                                        borderRadius: '6px',
                                        fontWeight: 'bold',
                                        fontSize: '14px'
                                    }}>
                                        <div style={{ 
                                            width: '16px', 
                                            height: '16px', 
                                            backgroundColor: '#f8d7da',
                                            border: '1px solid #f5c2c7',
                                            borderRadius: '3px'
                                        }}></div>
                                        0-50%: Poor
                                    </div>
                                </div>

                                <div className="card" style={{ marginTop: '1.5rem', width: '100%', textAlign: 'center' }}>
                                    <h4>Top Candidates Summary</h4>
                                    
                                    {/* Top Candidates Input */}
                                    <div style={{ 
                                        marginBottom: '1.5rem',
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                        gap: '1rem'
                                    }}>
                                        <label style={{ 
                                            fontSize: '1rem', 
                                            fontWeight: 'bold', 
                                            color: 'var(--color-text)' 
                                        }}>
                                            Show top
                                        </label>
                                        <input
                                            type="number"
                                            min="1"
                                            max="10"
                                            value={topCandidatesCount}
                                            onChange={(e) => setTopCandidatesCount(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))}
                                            style={{
                                                width: '80px',
                                                padding: '0.5rem',
                                                fontSize: '1rem',
                                                border: '1px solid var(--color-border)',
                                                borderRadius: '4px',
                                                textAlign: 'center'
                                            }}
                                        />
                                        <span style={{ 
                                            fontSize: '1rem', 
                                            color: 'var(--color-text)' 
                                        }}>
                                            candidates
                                        </span>
                                    </div>

                                    {/* Top Candidates Display */}
                                    <div style={{ 
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: '1rem',
                                        marginTop: '1rem'
                                    }}>
                                        {getSortedResumes().slice(0, topCandidatesCount).map((resume, index) => (
                                            <div key={index} style={{ 
                                                padding: '1.5rem', 
                                                backgroundColor: 'var(--color-card)', 
                                                borderRadius: '8px', 
                                                border: '1px solid var(--color-border)',
                                                textAlign: 'left'
                                            }}>
                                                <div style={{ 
                                                    display: 'flex', 
                                                    justifyContent: 'space-between', 
                                                    alignItems: 'center',
                                                    marginBottom: '1rem'
                                                }}>
                                                    <div style={{ 
                                                        display: 'flex', 
                                                        alignItems: 'center', 
                                                        gap: '1rem' 
                                                    }}>
                                                        <div style={{ 
                                                            width: '40px', 
                                                            height: '40px', 
                                                            borderRadius: '50%', 
                                                            backgroundColor: index === 0 ? '#ffd700' : index === 1 ? '#c0c0c0' : '#cd7f32',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            color: 'white',
                                                            fontWeight: 'bold',
                                                            fontSize: '1.2rem'
                                                        }}>
                                                            {index + 1}
                                                        </div>
                                                        <div>
                                                            <div style={{ 
                                                                fontSize: '1.3rem', 
                                                                fontWeight: 'bold', 
                                                                color: 'var(--color-text)',
                                                                marginBottom: '0.25rem'
                                                            }}>
                                                                {resume.resume_name}
                                                            </div>
                                                            <div style={{ 
                                                                fontSize: '1.1rem', 
                                                                color: '#2b78e4',
                                                                fontWeight: 'bold'
                                                            }}>
                                                                Score: {(resume.overall_score * 10).toFixed(1)}%
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                                
                                                <div style={{ 
                                                    fontSize: '1rem',
                                                    lineHeight: '1.6',
                                                    color: 'var(--color-text)',
                                                    backgroundColor: 'var(--color-secondary)',
                                                    padding: '1rem',
                                                    borderRadius: '6px',
                                                    border: '1px solid var(--color-border)'
                                                }}>
                                                    <strong>Overall Rationale:</strong><br />
                                                    {resume.overall_rationale || 'No overall rationale available'}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Scoring Rubric Legend */}
                                <div className="card" style={{ marginTop: '1.5rem', width: '100%', textAlign: 'center' }}>
                                    <h4>Scoring Rubric</h4>
                                    <div style={{ overflowX: 'auto' }}>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
                                            <thead>
                                                <tr style={{ backgroundColor: '#333', color: 'white' }}>
                                                    <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #555' }}>Rating</th>
                                                    <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #555' }}>Points</th>
                                                    <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #555' }}>Scale</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-text)' }}>A</td>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>9 – 10</td>
                                                    <td style={{ padding: '10px', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>Much more than acceptable behavior/skills</td>
                                                </tr>
                                                <tr>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-text)' }}>B</td>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>8</td>
                                                    <td style={{ padding: '10px', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>More than acceptable behavior/skills</td>
                                                </tr>
                                                <tr>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-text)' }}>C</td>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>7</td>
                                                    <td style={{ padding: '10px', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>Benchmark/behavior meets requirements</td>
                                                </tr>
                                                <tr>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-text)' }}>D</td>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>6</td>
                                                    <td style={{ padding: '10px', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>Less than acceptable behavior/skills</td>
                                                </tr>
                                                <tr>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-text)' }}>E</td>
                                                    <td style={{ padding: '10px', textAlign: 'center', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>1 – 5</td>
                                                    <td style={{ padding: '10px', border: '1px solid var(--color-border)', color: 'var(--color-text)' }}>Much less than acceptable behavior/skills</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                    <div style={{ marginTop: '1rem', padding: '10px', backgroundColor: 'var(--color-secondary)', borderRadius: '4px', border: '1px solid var(--color-primary)', color: 'var(--color-text)' }}>
                                        <strong>Overall Score:</strong> The final score is calculated as a percentage based on the weighted average of all criteria scores.
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Bottom Navigation Bar */}
            <div style={{ 
                backgroundColor: 'var(--color-secondary)', 
                padding: '1rem 2rem',
                borderTop: '1px solid var(--color-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: '2rem',
                borderRadius: '8px'
            }}>
                <button 
                    onClick={() => {
                        if (activeTab === 'criteria') setActiveTab('upload');
                        if (activeTab === 'results') setActiveTab('criteria');
                    }}
                    disabled={activeTab === 'upload'}
                    style={{ 
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.75rem 1.5rem',
                        backgroundColor: activeTab === 'upload' ? 'var(--color-border)' : 'var(--color-card)',
                        color: activeTab === 'upload' ? 'var(--color-muted)' : 'var(--color-text)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '6px',
                        cursor: activeTab === 'upload' ? 'not-allowed' : 'pointer',
                        opacity: activeTab === 'upload' ? 0.5 : 1
                    }}
                >
                    ← Previous
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <span style={{ color: 'var(--color-muted)', fontSize: '0.9rem' }}>
                        Step {activeTab === 'upload' ? '1' : activeTab === 'criteria' ? '2' : '3'} of 3
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <div style={{ 
                            width: '8px', 
                            height: '8px', 
                            borderRadius: '50%', 
                            backgroundColor: activeTab === 'upload' ? 'var(--color-primary)' : 'var(--color-border)'
                        }}></div>
                        <div style={{ 
                            width: '8px', 
                            height: '8px', 
                            borderRadius: '50%', 
                            backgroundColor: activeTab === 'criteria' ? 'var(--color-primary)' : 'var(--color-border)'
                        }}></div>
                        <div style={{ 
                            width: '8px', 
                            height: '8px', 
                            borderRadius: '50%', 
                            backgroundColor: activeTab === 'results' ? 'var(--color-primary)' : 'var(--color-border)'
                        }}></div>
                    </div>
                </div>

                <button 
                    onClick={() => {
                        if (activeTab === 'upload') setActiveTab('criteria');
                        if (activeTab === 'criteria') setActiveTab('results');
                    }}
                    disabled={activeTab === 'results'}
                    style={{ 
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        padding: '0.75rem 1.5rem',
                        backgroundColor: activeTab === 'results' ? 'var(--color-border)' : 'var(--color-primary)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: activeTab === 'results' ? 'not-allowed' : 'pointer',
                        opacity: activeTab === 'results' ? 0.5 : 1
                    }}
                >
                    Next →
                </button>
            </div>

            {/* Citation Modal */}
            <CitationModal
                isOpen={citationModal.isOpen}
                onClose={closeCitationModal}
                citation={citationModal.citation}
                workspaceName={workspaceName}
                resumeName={citationModal.resumeName}
                criterionName={citationModal.criterionName}
                rationale={citationModal.rationale}
            />
        </div>
    );
};

export default ResumeScoringMode;
