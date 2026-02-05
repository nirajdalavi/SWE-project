# Async Job Queue Implementation Guide

## 🎯 Overview

The Redis job queue system solves Cloudflare 524 timeout issues by processing long-running tasks asynchronously. This guide shows how to implement the async pattern in your frontend.

## 🔧 Backend Changes (Already Implemented)

### ✅ What's Already Done:
- Redis JobManager with job creation, status tracking, and result storage
- Background worker thread processing jobs
- Enhanced endpoints supporting `async_mode=true` parameter
- Comprehensive logging for job lifecycle

### 📋 Supported Async Endpoints:
- `POST /score?async_mode=true` - Contract scoring
- `POST /audit?async_mode=true` - Contract auditing
- `POST /jobs/{job_type}` - Generic job creation
- `GET /jobs/{job_id}` - Job status checking
- `GET /worker/status` - Worker health check

## 🎨 Frontend Implementation

### ✅ **What's Already Implemented:**

1. **Updated API Service** (`frontend/src/services/api.js`)

```javascript
// Async scoring with optional async mode
export const scoreContracts = (criterion, workspaceName, maxScore, compareChatgpt, shareDataWithChatgpt, asyncMode = false) =>
  api.post('/score', 
    { criterion, workspace_name: workspaceName, max_score: maxScore, compare_chatgpt: compareChatgpt, share_data_with_chatgpt: shareDataWithChatgpt },
    { params: { async_mode: asyncMode } }
  );

// Job queue endpoints
export const createJob = (jobType, payload) => api.post(`/jobs/${jobType}`, payload);
export const getJobStatus = (jobId) => api.get(`/jobs/${jobId}`);
export const getWorkerStatus = () => api.get('/worker/status');

// Polling utility
export const pollJobStatus = async (jobId, onProgress, onComplete, onError, pollInterval = 2000, maxAttempts = 150) => {
  // Handles automatic polling with callbacks
};
```

2. **Enhanced ScoreContractsMode Component** (`frontend/src/components/ScoreContractsMode.js`)
   - ✅ Async mode enabled by default (no UI toggle)
   - ✅ Silent background polling for job completion
   - ✅ No timeout issues - seamless user experience
   - ✅ No new files required - everything integrated into existing component

**Key Features Added:**
- Async mode always enabled (invisible to user)
- Silent background polling (no progress UI)
- Automatic job completion handling
- Fallback to synchronous mode if needed

### 3. **Migration Strategy**

#### Option A: Gradual Migration (Recommended)
1. Add async mode as optional parameter (default `false`)
2. Update UI components to use async mode for long operations
3. Keep synchronous mode as fallback

#### Option B: Full Async Migration
1. Set `asyncMode = true` by default for all long operations
2. Update all components to use polling pattern
3. Remove synchronous fallbacks

## 🚀 Usage Examples

### **Basic Async Scoring:**
```javascript
// Start async scoring
const response = await scoreContracts(criterion, workspaceName, maxScore, false, false, true);
const { job_id } = response.data;

// Poll for completion
pollJobStatus(
  job_id,
  (job) => console.log('Progress:', job.status),
  (result) => console.log('Complete:', result),
  (error) => console.error('Error:', error)
);
```

### **Using the Hook:**
```javascript
const scoringJob = useAsyncJob();

const startScoring = () => {
  scoringJob.startJob(() => 
    scoreContracts(criterion, workspaceName, maxScore, false, false, true)
  );
};

// scoringJob.isLoading - boolean
// scoringJob.progress - { status, message, jobId }
// scoringJob.result - final results
// scoringJob.error - error message
```

### **Direct Job Creation:**
```javascript
// Create custom job
const response = await createJob('score_contracts', {
  criterion: 'Your criteria...',
  workspace_name: 'test',
  max_score: 100,
  compare_chatgpt: false,
  share_data_with_chatgpt: false
});

const { job_id } = response.data;
```

## 📊 Job Status Flow

```
PENDING → STARTED → SUCCESS/FAILURE
   ↓         ↓           ↓
Queued   Processing   Complete
```

### Status Messages:
- `PENDING`: "Job queued, waiting to start..."
- `STARTED`: "Processing in progress..."
- `SUCCESS`: "Completed successfully!"
- `FAILURE`: "Job failed"

## 🔍 Monitoring & Debugging

### **Check Worker Status:**
```javascript
const workerStatus = await getWorkerStatus();
console.log(workerStatus.data);
// {
//   status: "running",
//   redis_connected: true,
//   jobs_in_queue: 2,
//   worker_thread_alive: true
// }
```

### **Backend Logs to Watch:**
```
INFO:main:[Main] Starting Redis worker thread...
INFO:main:[Worker] Redis worker thread started and ready to process jobs
INFO:main:[/score] 🔄 Async mode: Job abc123... queued for workspace 'test'
INFO:main:[Worker] 🚀 Starting job abc123... type=score_contracts for workspace=test
INFO:main:[Worker] ✅ Job abc123... completed successfully
```

## 🎯 Benefits

- ✅ **No more 524 timeouts** - Requests return immediately
- ✅ **Better UX** - Users get immediate feedback
- ✅ **Scalable** - Can handle multiple concurrent jobs
- ✅ **Reliable** - Jobs persist through server restarts
- ✅ **Monitorable** - Full logging and status tracking

## 🔧 Configuration

### **Polling Settings:**
- `pollInterval`: 2000ms (2 seconds)
- `maxAttempts`: 150 (5 minutes timeout)

### **Redis Configuration:**
- Default: `redis://localhost:6379/0`
- Environment: `REDIS_URL`

## 🚨 Error Handling

The system handles:
- Redis connection failures
- Job processing errors
- Timeout scenarios
- Invalid job types
- Missing jobs

All errors are properly logged and returned to the frontend.

## 📝 Next Steps

1. **Update existing components** to use `asyncMode=true` for long operations
2. **Add progress indicators** using the `useAsyncJob` hook
3. **Test with real workloads** to verify timeout resolution
4. **Monitor backend logs** for job processing
5. **Consider adding job cancellation** for user-initiated stops

This implementation provides a robust solution for handling long-running operations without timeout issues! 🎉
