import React, { useState, useEffect, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import '../styles/pdf/AnnotationLayer.css';
import '../styles/pdf/TextLayer.css';
import { ErrorBoundary } from 'react-error-boundary';

// Make sure pdf.worker.min.mjs is in your /public folder!
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

function PdfViewerComponent({ workspaceName, fileName, initialPage, onClose }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(initialPage || 1);
  const [loadingPdf, setLoadingPdf] = useState(true);
  const [pdfError, setPdfError] = useState(null);
  const [fileUrl, setFileUrl] = useState(null);
  const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost'; // Fallback to local if not set

  useEffect(() => {
    // Cleanup old object URL
    return () => {
      if (fileUrl) {
        URL.revokeObjectURL(fileUrl);
      }
    };
  }, [fileUrl]);

  useEffect(() => {
    setLoadingPdf(true);
    setPdfError(null);
    setFileUrl(null);

    // Construct URL properly for both local and production environments
    let pdfApiUrl;
    if (backendHost === 'localhost') {
      // Local development
      pdfApiUrl = `http://${backendHost}:8000/pdf/${workspaceName}/${fileName}`;
    } else {
      // Production - handle both cases where backendHost includes protocol or not
      if (backendHost.startsWith('http')) {
        pdfApiUrl = `${backendHost}/api/pdf/${workspaceName}/${fileName}`;
      } else {
        pdfApiUrl = `https://${backendHost}/api/pdf/${workspaceName}/${fileName}`;
      }
    }
    fetch(pdfApiUrl)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setFileUrl(url);
        setLoadingPdf(false);
      })
      .catch(err => {
        setPdfError(`Failed to load PDF: ${err.message}`);
        setLoadingPdf(false);
      });
  }, [workspaceName, fileName]);

  const onDocumentLoadSuccess = useCallback((pdf) => {
    setNumPages(pdf.numPages);
    setLoadingPdf(false);
    if (initialPage && initialPage > 0 && initialPage <= pdf.numPages) {
      setPageNumber(initialPage);
    } else {
      setPageNumber(1);
    }
  }, [initialPage]);

  const onDocumentLoadError = useCallback((error) => {
    setPdfError(`Failed to load PDF: ${error.message || error.toString()}`);
    setLoadingPdf(false);
  }, []);

  const goToPrevPage = () => setPageNumber(prevPage => Math.max(prevPage - 1, 1));
  const goToNextPage = () => setPageNumber(prevPage => Math.min(prevPage + 1, numPages));

  return (
    <div style={{
      border: '1px solid #ddd',
      borderRadius: '8px',
      margin: '2em auto',
      padding: '15px',
      backgroundColor: '#f9f9f9',
      boxShadow: '0 2px 5px rgba(0,0,0,0.1)',
      maxWidth: '800px',
      width: '100%'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h4 style={{ margin: 0 }}>
          File: {fileName} (Page {pageNumber} of {numPages || '...'})
        </h4>
        <button onClick={onClose} style={{
          padding: '8px 15px',
          backgroundColor: '#dc3545',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer'
        }}>
          Hide Source
        </button>
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
        <button onClick={goToPrevPage} disabled={pageNumber <= 1 || loadingPdf} style={{
          padding: '8px 15px',
          marginRight: '5px',
          backgroundColor: '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer'
        }}>
          Previous
        </button>
        <button onClick={goToNextPage} disabled={pageNumber >= numPages || loadingPdf} style={{
          padding: '8px 15px',
          backgroundColor: '#007bff',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer'
        }}>
          Next
        </button>
      </div>

      <div style={{ border: '1px solid #ccc', overflow: 'auto', maxHeight: '500px', backgroundColor: 'white' }}>
      {loadingPdf && <p style={{ textAlign: 'center', padding: '20px' }}>Loading PDF...</p>}
      {pdfError && <p style={{ color: 'red', textAlign: 'center', padding: '20px' }}>{pdfError}</p>}
      {!loadingPdf && !pdfError && fileUrl && (
        <ErrorBoundary fallback={<div>Could not load PDF.</div>}>
          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            // options={{ workerSrc: pdfjs.GlobalWorkerOptions.workerSrc }}
          >
            <Page
              pageNumber={pageNumber}
              renderTextLayer={true}
              renderAnnotationLayer={true}
              width={550}
            />
          </Document>
        </ErrorBoundary>
        )}
       </div>
    </div>
  );
}

export default PdfViewerComponent;
