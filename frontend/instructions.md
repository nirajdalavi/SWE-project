# Allyin Compass Frontend Coding Instructions

## Goal
Implement the remaining frontend React components to connect to the FastAPI backend for contract question-answering and scoring.

## Directories
**Project Root:** `frontend/`

- Components go in: `src/components/`
- API helper in: `src/services/api.js`
- Main app: `src/App.js`

## Files to Create
- `src/components/AskQuestionMode/index.jsx`
- `src/components/ScoreContractsMode/index.jsx`
- `src/components/FileUpload.jsx`

## Files to Update
- `src/services/api.js` — confirm all backend routes match.
- `src/App.js` — import and wire new components.

## Files Not to Edit
- `WorkspaceSelector.js` (unless explicitly asked)
- `App.css` (unless adding minor styles)

## Functionality Requirements

1. **AskQuestionMode**
   - Textarea to enter a question.
   - Button to submit (`askQuestion()`).
   - Show:
     - Allyn (OpenRouter) response
     - ChatGPT response
     - List of sources
   - Loading and error states.

2. **ScoreContractsMode**
   - Textarea for criteria.
   - Number input for max score.
   - Button to submit (`scoreContracts()`).
   - Show:
     - Final scores (OpenRouter & ChatGPT)
     - Summary of best contract
   - Loading and error states.

3. **FileUpload**
   - Props: `workspaceName`, `type` ("documents" or "criteria")
   - Multiple file input and upload button.
   - Show uploaded filenames.

4. **App.js**
   - Render modes:
     ```jsx
     {mode === 'ask' && selectedWorkspace && (
       <AskQuestionMode workspaceName={selectedWorkspace} />
     )}
     {mode === 'score' && selectedWorkspace && (
       <ScoreContractsMode workspaceName={selectedWorkspace} />
     )}
     ```

5. **api.js**
   - All endpoints must point to `http://localhost:8000` with proper routes.

## Styling
Basic styling is acceptable for now. Advanced styling will be applied later.

## Testing
Use these steps:
- Create a workspace.
- Upload PDFs.
- Ask a question.
- Upload criteria.
- Score contracts.

## Notes
- Keep code in functional components with hooks.
- Use async/await and try/catch for API calls.
