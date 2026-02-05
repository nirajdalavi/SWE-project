// frontend/src/components/CombinedEvaluationMode.js
import React, { useState, useEffect, useRef } from 'react';
import { combinedEvaluate, submitAdmin, exportCombinedReport } from '../services/api';
import './ScoreContractsMode.css'; // This CSS file will be used for styling
import FinalScoresTable from './FinalScoresTable';
import BestProposalSummary from './BestProposalSummary';
import CombinedScoreTable from "./CombinedScoreTable";
import FileUpload from './FileUpload'; // Ensure FileUpload is imported

function CombinedEvaluationMode({ workspaceName, setLoading, loading, mode,progressSteps, currentStepIndex, setProgressSteps, setCurrentStepIndex }) {
  const [technicalWeight, setTechnicalWeight] = useState(50);
  const [financialWeight, setFinancialWeight] = useState(50);
  const [combinedResults, setCombinedResults] = useState(null);
  const [error, setError] = useState('');
  const [adminComment, setAdminComment] = useState('');

  const combinedScoreTableRef = useRef(null);

  const isInitialMount = useRef(true);

  useEffect(() => {
    // Reset state when workspace changes
    setTechnicalWeight(50);
    setFinancialWeight(50);
    setCombinedResults(null);
    setError('');
    setAdminComment('');
    isInitialMount.current = true;
  }, [workspaceName]);

  // FIX HERE: REMOVE combinedResults from the dependency array
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const techW = parseFloat(technicalWeight);
    const finW = parseFloat(financialWeight);

    // Only run if both weights are valid numbers and sum to 100
    // And, importantly, only run if combinedResults has been set at least once
    // This check is important to prevent an evaluation call immediately on mount
    // if there's no pre-existing data from a prior session.
    if (!isNaN(techW) && !isNaN(finW) && (techW + finW === 100) && combinedResults !== null) {
        const handler = setTimeout(() => {
            // Use a functional update for combinedResults if needed, or
            // ensure handleCombinedEvaluation doesn't cause a re-render.
            // A common pattern here is to pass a 'callback' for handleCombinedEvaluation
            // or ensure the function itself is stable.
            handleCombinedEvaluation(null); // Call the evaluation handler
        }, 500);

        return () => {
            clearTimeout(handler);
        };
    }
  }, [technicalWeight, financialWeight, workspaceName]); // <--- KEY CHANGE: Removed combinedResults


  const handleTechnicalWeightChange = (e) => {
    const value = parseInt(e.target.value);
    if (!isNaN(value) && value >= 0 && value <= 100) {
      setTechnicalWeight(value);
      setFinancialWeight(100 - value);
    } else if (e.target.value === '') {
      setTechnicalWeight('');
      setFinancialWeight('');
    }
  };

  const handleFinancialWeightChange = (e) => {
    const value = parseInt(e.target.value);
    if (!isNaN(value) && value >= 0 && value <= 100) {
      setFinancialWeight(value);
      setTechnicalWeight(100 - value);
    } else if (e.target.value === '') {
      setFinancialWeight('');
      setTechnicalWeight('');
    }
  };

  const handleCombinedEvaluation = async (e) => {
    if (e) {
        e.preventDefault();
    }
    
    setLoading(true);
    setError('');
    // setCombinedResults(null); // Keep commented out as discussed

    const techW = parseFloat(technicalWeight);
    const finW = parseFloat(financialWeight);

    if (isNaN(techW) || isNaN(finW) || (techW + finW !== 100 && (techW !== 0 || finW !== 0))) {
      setError("Technical and Financial weights must be numbers and sum to 100.");
      setLoading(false);
      return;
    }

    try {
      const { data } = await combinedEvaluate(workspaceName, techW, finW);
      setCombinedResults(data); // This update is what caused the loop
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to perform combined evaluation.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitToAdmin = async () => {
    setLoading(true);
    try {
      await submitAdmin(workspaceName, adminComment, mode);
      alert("Combined evaluation submitted to admin successfully!");
    } catch (err) {
      console.error("Error submitting combined evaluation to admin:", err);
      alert(
        err.response?.data?.detail ||
        err.message ||
        "Failed to submit combined evaluation to admin."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleExportReport = async () => {
    setLoading(true);
    try {
      // Default to English for now, can be enhanced later with language selection
      const response = await exportCombinedReport(workspaceName, 'en');
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${workspaceName}_combined_evaluation_report.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      alert("Combined report exported successfully!");
    } catch (err) {
      console.error("Error exporting combined report:", err);
      alert(`Failed to export combined report: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };


  const renderAdminApprovalCard = () => (
    <div className="card" style={{ marginTop: '2em', padding: '1.5em', borderRadius: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.5em' }}>
        <div style={{ width: 12, height: 12, backgroundColor: '#f4b400', borderRadius: '3px', marginRight: 10 }}></div>
        <h4 className="card-title" style={{ margin: 0 }}>Submit Combined Evaluation for Admin Approval</h4>
      </div>

      <p className="small-text" style={{ marginBottom: '1em' }}>
        Combined evaluation complete. Ready for final review and decision.
      </p>

      <textarea
        placeholder="Add comments for the admin reviewer (optional)..."
        rows="3"
        className="input-field"
        disabled={loading}
        value={adminComment}
        onChange={(e) => setAdminComment(e.target.value)}
        style={{
          width: '100%',
          marginBottom: '1em'
        }}
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
          disabled={!combinedResults || loading}
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
          disabled={!combinedResults || loading}
        >
          💾 Export Report
        </button>
      </div>
    </div>
  );


  return (
    <div className="combined-evaluation-mode">

      <div className="card">
        <h3 className="card-title">Configure Combined Evaluation</h3>
        <form onSubmit={handleCombinedEvaluation}>
          <div style={{ marginBottom: '1em' }}>
            <label htmlFor="technical-weight" className="small-text" style={{ display: 'block', marginBottom: '5px' }}>Technical Report Weight (%):</label>
            <input
              type="number"
              id="technical-weight"
              value={technicalWeight}
              onChange={handleTechnicalWeightChange}
              min="0"
              max="100"
              step="1"
              className="input-field"
              disabled={loading}
              style={{ marginBottom: '1em' }}
            />
          </div>
          <div style={{ marginBottom: '1em' }}>
            <label htmlFor="financial-weight" className="small-text" style={{ display: 'block', marginBottom: '5px' }}>Financial Report Weight (%):</label>
            <input
              type="number"
              id="financial-weight"
              value={financialWeight}
              onChange={handleFinancialWeightChange}
              min="0"
              max="100"
              step="1"
              className="input-field"
              disabled={loading}
              style={{ marginBottom: '1em' }}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="button gradient-button"
          >
            {loading ? 'Evaluating...' : 'Run Combined Evaluation'}
          </button>
        </form>
      </div>

      {error && (
        <p className="error-message">Error: {error}</p>
      )}

      {/* NEW FLEX CONTAINER FOR FILE UPLOADS */}
      <div className="file-upload-sections-container">
        {/* File Upload: Technical Report */}
        <div className="file-upload-card card">
          <FileUpload
            key="upload-technical-report"
            workspaceName={workspaceName}
            fileType="technical_report"
            onUploadSuccess={() => console.log("Technical report uploaded")}
          />
        </div>
        {/* File Upload: Financial Report */}
        <div className="file-upload-card card">
          <FileUpload
            key="upload-financial-report"
            workspaceName={workspaceName}
            fileType="financial_report"
            onUploadSuccess={() => console.log("Financial report uploaded")}
          />
        </div>
      </div>

      {combinedResults && (
        <>
          {combinedResults.raw_combined && combinedResults.raw_combined.contracts && (
            <CombinedScoreTable
              ref={combinedScoreTableRef}
              contracts={combinedResults.raw_combined.contracts}
              title="Combined Breakdown"
              loading={loading}
              setLoading={setLoading}
              type="combined"
              workspaceName={workspaceName}
            />
          )}

          {combinedResults.final_scores_combined && (
            <FinalScoresTable
              workspaceName={workspaceName}
              initialOpenrouterScores={combinedResults.final_scores_combined}
              initialChatgptScores={{}}
              compareResponsesEnabled={false}
              loading={loading}
              setLoading={setLoading}
            />
          )}

          {combinedResults.summary_of_combined_best && (
            <BestProposalSummary
              workspaceName={workspaceName}
              initialSummary={combinedResults.summary_of_combined_best}
              loading={loading}
              setLoading={setLoading}
            />
          )}

          {renderAdminApprovalCard()}
        </>
      )}
    </div>
  );
}

export default CombinedEvaluationMode;