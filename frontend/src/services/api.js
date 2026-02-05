
// frontend/src/services/api.js
import axios from 'axios';

// Base URL for your FastAPI backend
const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost'; 
const API_BASE_URL = backendHost.startsWith('http') ? `${backendHost}/api` : `http://${backendHost}:8000`;

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// --- Workspace Endpoints ---
export const getWorkspaces = () => api.get('/workspaces');
export const createWorkspace = (workspaceName) => api.post('/workspaces', { workspace_name: workspaceName });
export const deleteWorkspace = (workspaceName) => api.delete(`/workspaces/${workspaceName}`);

// --- QA & Scoring Endpoints ---
export const askQuestion = (query, workspaceName, responseSize, responseType, compareChatgpt, shareDataWithChatgpt, useWeb = false, specificUrl = '', asyncMode = true) =>
  api.post('/qa', 
    {
      query,
      workspace_name: workspaceName,
      response_size: responseSize,
      response_type: responseType,
      compare_chatgpt: compareChatgpt,
      share_data_with_chatgpt: shareDataWithChatgpt,
      use_web: useWeb,
      specific_url: specificUrl
    },
    { params: { async_mode: asyncMode } }
  );

export const scoreContracts = (criterion, workspaceName, maxScore, compareChatgpt, shareDataWithChatgpt, asyncMode = true) =>
  api.post('/score', 
    { criterion, workspace_name: workspaceName, max_score: maxScore, compare_chatgpt: compareChatgpt, share_data_with_chatgpt: shareDataWithChatgpt },
    { params: { async_mode: asyncMode } }
  );

export const getContractScores = (workspaceName) => 
  api.get(`/contract-scores/${workspaceName}`);

// --- Job Queue Endpoints ---
export const createJob = (jobType, payload) =>
  api.post(`/jobs/${jobType}`, payload);

export const getJobStatus = (jobId) =>
  api.get(`/jobs/${jobId}`);

export const getWorkerStatus = () =>
  api.get('/worker/status');

// --- Job Polling Utilities ---
export const pollJobStatus = async (jobId, onProgress, onComplete, onError, pollInterval = 3000, maxAttempts = 600) => {
  let attempts = 0;
  
  const poll = async () => {
    try {
      attempts++;
      const response = await getJobStatus(jobId);
      const job = response.data;
      
      // Call progress callback with current status
      if (onProgress) {
        onProgress(job);
      }
      
      // Check if job is complete
      if (job.status === 'SUCCESS') {
        if (onComplete) {
          onComplete(job.result);
        }
        return;
      } else if (job.status === 'FAILURE') {
        if (onError) {
          onError(new Error(job.error || 'Job failed'));
        }
        return;
      } else if (job.status === 'NOT_FOUND') {
        if (onError) {
          onError(new Error('Job not found'));
        }
        return;
      }
      
      // Continue polling if job is still in progress
      if (attempts < maxAttempts) {
        setTimeout(poll, pollInterval);
      } else {
        if (onError) {
          onError(new Error('Job polling timeout'));
        }
      }
    } catch (error) {
      if (onError) {
        onError(error);
      }
    }
  };
  
  // Start polling
  poll();
};

export const compareResponses = (openrouterResponse, chatgptResponse) => api.post('/compare_responses', { openrouter_response: openrouterResponse, chatgpt_response: chatgptResponse });
export const submitAdmin = (workspaceName, comment, mode) =>
  api.post('/submit_admin', {
    workspace_name: workspaceName,
    comment: comment,
    mode: mode
  });

export const saveEditedScores = (workspaceName, editedData) =>
  api.post(`/save_edited_scores/${workspaceName}`, editedData);

export const exportReport = (workspaceName, language = 'en') =>
  api.get(`/export_report/${workspaceName}`, { 
    responseType: 'blob',
    params: { language }
  });



export const exportCombinedReport = (workspaceName, language = 'en') => {
  return api.get(`${API_BASE_URL}/export_combined_report/${workspaceName}`, { 
    responseType: 'blob',
    params: { language }
  });
};

export const exportTableXLSX = (workspaceName, contracts, title) => {
  return api.post(
      `${API_BASE_URL}/export_table_xlsx/${workspaceName}`,
      { contracts, title }, // Send the contracts data and title
      { responseType: 'blob' }
  );
};
// NEW: Combined Evaluation Endpoint
export const combinedEvaluate = (workspaceName, technicalWeight, financialWeight) =>
  api.post('/combined_evaluate', {
    workspace_name: workspaceName,
    technical_weight: technicalWeight,
    financial_weight: financialWeight
  });

// --- Upload Endpoints ---
export const uploadFiles = async (workspaceName, files, fileType = 'documents') => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    const endpoint =
      fileType === 'criteria'
        ? `/upload/criteria/${workspaceName}`
        : fileType === 'technical_report' // NEW: Technical Report upload
        ? `/upload/technical_report/${workspaceName}`
        : fileType === 'financial_report' // NEW: Financial Report upload
        ? `/upload/financial_report/${workspaceName}`
        : fileType === 'job_description' // NEW: Job Description upload
        ? `/upload-jd/${workspaceName}`
        : fileType === 'resumes' // NEW: Resumes upload
        ? `/upload-resume/${workspaceName}`
        : `/upload/documents/${workspaceName}`;

    return api.post(endpoint, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
};

// --- Prompts Endpoints ---
export const getPrompts = (workspaceName) => api.get(`/prompts/${workspaceName}`);

// --- Other Utility Endpoints ---
export const getPdf = (workspaceName, fileName) => api.get(`/pdf/${workspaceName}/${fileName}`, { responseType: 'blob' });
export const getMetrics = (workspaceName) => api.get(`/metrics/${workspaceName}`);
export const getProcessingStatus = (workspaceName) => api.get(`/processing_status/${workspaceName}`);

// --- Translation Endpoint ---
export const translateText = (text, targetLanguage) => 
  api.post('/api/translate', {
    text: text,
    target_language: targetLanguage
  });

// --- Resume Scoring Endpoints ---
export const uploadResume = (workspaceName, formData) =>
  api.post(`/upload-resume/${workspaceName}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

export const uploadJobDescription = (workspaceName, formData) =>
  api.post(`/upload-jd/${workspaceName}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

export const getResumeCriteria = (workspaceName) => 
  api.get(`/resume-criteria/${workspaceName}`);

export const getResumeCriteriaRaw = (workspaceName) => 
  api.get(`/resume-criteria-raw/${workspaceName}`);

export const testCriteriaExtraction = (workspaceName) => 
  api.post(`/test-criteria-extraction/${workspaceName}`);

export const updateResumeCriteria = (workspaceName, criteriaData) =>
  api.post(`/update-resume-criteria/${workspaceName}`, criteriaData);

export const scoreResumes = (workspaceName, asyncMode = true) =>
  api.post(`/score-resumes/${workspaceName}`, {}, { params: { async_mode: asyncMode } });

export const getResumeScores = (workspaceName) =>
  api.get(`/resume-scores/${workspaceName}`);

export const saveResumeScores = (workspaceName, data) =>
  api.post(`/save-resume-scores/${workspaceName}`, data);

export const getResumeFiles = (workspaceName) =>
  api.get(`/resume-files/${workspaceName}`);

export const getJdFiles = (workspaceName) =>
  api.get(`/jd-files/${workspaceName}`);

export const sendResumeEmail = (workspaceName, emailData) =>
  api.post(`/send-resume-email/${workspaceName}`, emailData);

export const getResumeCitation = (workspaceName, resumeName, criterionName) =>
  api.get(`/resume-citation/${workspaceName}`, {
    params: {
      resume_name: resumeName,
      criterion_name: criterionName
    }
  });

export const getGoogleDriveAuthUrl = (workspaceName) => {
  return api.get(`/gdrive/auth/${encodeURIComponent(workspaceName)}`);
};

// Feature Request endpoint
export const submitFeatureRequest = (featureData) => 
  api.post('/api/feature-request', featureData);

// Contact Form endpoint
export const submitContactForm = (contactData) => 
  api.post('/api/contact', contactData);

export const getGoogleDriveAuthStatus = (workspaceName) => {
  return api.get(`/google-drive/status/${encodeURIComponent(workspaceName)}`);
};

export const revokeGoogleDriveAccess = (workspaceName) => {
  return api.post(`/google-drive/revoke/${encodeURIComponent(workspaceName)}`);
};

export const listGoogleDriveFolders = (workspaceName, parentId = null) => {
  const params = new URLSearchParams();
  if (parentId) params.append('parent_id', parentId);
  const qs = params.toString();
  return api.get(`/google-drive/folders/${encodeURIComponent(workspaceName)}${qs ? `?${qs}` : ''}`);
};

// If fileTypesCsv is null/empty, we DO NOT send any file_types params so backend returns ALL files.
export const listGoogleDriveFiles = (folderId = null, fileTypesCsv = null, workspaceName = null) => {
  const params = new URLSearchParams();
  if (folderId) params.append('folder_id', folderId);
  if (fileTypesCsv && String(fileTypesCsv).trim().length > 0) {
    const items = Array.isArray(fileTypesCsv)
      ? fileTypesCsv
      : String(fileTypesCsv).split(',').map(s => s.trim()).filter(Boolean);
    for (const it of items) params.append('file_types', it);
  }
  const qs = params.toString();
  const url = `/google-drive/files/${encodeURIComponent(workspaceName)}${qs ? `?${qs}` : ''}`;
  return api.get(url);
};

export const uploadFromGoogleDrive = (workspaceName, fileIds, fileType) => {
  return api.post(`/gdrive/import`, {
    workspace_name: workspaceName,
    file_ids: Array.isArray(fileIds) ? fileIds : [fileIds],
    file_type: fileType
  });
};

// --- Audit Endpoints ---
export const performAudit = (workspaceName, asyncMode = true) =>
  api.post('/audit', 
    { workspace_name: workspaceName },
    { params: { async_mode: asyncMode } }
  );

export const getAuditResults = (workspaceName) =>
  api.get(`/audit-results/${workspaceName}`);

// --- Legal Analysis Endpoints ---
export const performLegalAnalysis = (workspaceName, asyncMode = true) =>
  api.post('/legal', 
    { workspace_name: workspaceName },
    { params: { async_mode: asyncMode } }
  );

export const getLegalResults = (workspaceName) =>
  api.get(`/legal-results/${workspaceName}`);


export default api;