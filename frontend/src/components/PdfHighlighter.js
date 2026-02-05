import React, { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { FaSearch, FaTimes } from 'react-icons/fa';
import '../styles/pdf/AnnotationLayer.css';
import '../styles/pdf/TextLayer.css';

// Make sure pdf.worker.min.mjs is in your /public folder!
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

const PdfHighlighter = ({ 
    workspaceName, 
    fileName, 
    highlightedTexts = [], 
    onClose,
    initialPage = 1 
}) => {
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(initialPage);
    const [loadingPdf, setLoadingPdf] = useState(true);
    const [pdfError, setPdfError] = useState(null);
    const [fileUrl, setFileUrl] = useState(null);
    const [highlightedElements, setHighlightedElements] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [currentSearchIndex, setCurrentSearchIndex] = useState(0);
    const [showSearch, setShowSearch] = useState(false);
    const backendHost = process.env.REACT_APP_BACKEND_HOST || 'localhost';

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
            // Production - use HTTPS and proper path
            pdfApiUrl = `https://${backendHost}/api/pdf/${workspaceName}/${fileName}`;
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

    useEffect(() => {
        if (!loadingPdf && highlightedTexts.length > 0) {
            // Wait for the PDF to render, then highlight text
            setTimeout(() => {
                highlightTextInPdf();
            }, 1000);
        }
    }, [loadingPdf, highlightedTexts]);

    const highlightTextInPdf = () => {
        const textLayer = document.querySelector('.react-pdf__Page__textContent');
        if (!textLayer) return;

        const textElements = textLayer.querySelectorAll('.react-pdf__Page__textContent span');
        const highlights = [];

        highlightedTexts.forEach((textToHighlight, index) => {
            const words = textToHighlight.toLowerCase().split(/\s+/);
            
            textElements.forEach((element) => {
                const elementText = element.textContent.toLowerCase();
                
                // Check if this element contains any of the words we want to highlight
                const hasMatch = words.some(word => 
                    elementText.includes(word) && word.length > 2
                );
                
                if (hasMatch) {
                    // Create highlight overlay
                    const rect = element.getBoundingClientRect();
                    const textLayerRect = textLayer.getBoundingClientRect();
                    
                    const highlight = document.createElement('div');
                    highlight.style.position = 'absolute';
                    highlight.style.left = `${rect.left - textLayerRect.left}px`;
                    highlight.style.top = `${rect.top - textLayerRect.top}px`;
                    highlight.style.width = `${rect.width}px`;
                    highlight.style.height = `${rect.height}px`;
                    highlight.style.backgroundColor = `hsl(${45 + index * 60}, 70%, 60%)`;
                    highlight.style.opacity = '0.3';
                    highlight.style.pointerEvents = 'none';
                    highlight.style.zIndex = '10';
                    highlight.style.borderRadius = '2px';
                    
                    textLayer.appendChild(highlight);
                    highlights.push(highlight);
                }
            });
        });

        setHighlightedElements(highlights);
    };

    const clearHighlights = () => {
        highlightedElements.forEach(element => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
        });
        setHighlightedElements([]);
    };

    const onDocumentLoadSuccess = (pdf) => {
        setNumPages(pdf.numPages);
        setLoadingPdf(false);
        if (initialPage && initialPage > 0 && initialPage <= pdf.numPages) {
            setPageNumber(initialPage);
        } else {
            setPageNumber(1);
        }
    };

    const onDocumentLoadError = (error) => {
        setPdfError(`Failed to load PDF: ${error.message || error.toString()}`);
        setLoadingPdf(false);
    };

    const goToPrevPage = () => {
        clearHighlights();
        setPageNumber(prevPage => Math.max(prevPage - 1, 1));
    };

    const goToNextPage = () => {
        clearHighlights();
        setPageNumber(prevPage => Math.min(prevPage + 1, numPages));
    };

    const toggleHighlights = () => {
        if (highlightedElements.length > 0) {
            clearHighlights();
        } else {
            highlightTextInPdf();
        }
    };

    const performSearch = () => {
        if (!searchTerm.trim()) return;
        
        clearHighlights();
        const textLayer = document.querySelector('.react-pdf__Page__textContent');
        if (!textLayer) return;

        const textElements = textLayer.querySelectorAll('.react-pdf__Page__textContent span');
        const results = [];
        const highlights = [];

        textElements.forEach((element) => {
            const elementText = element.textContent.toLowerCase();
            const searchLower = searchTerm.toLowerCase();
            
            if (elementText.includes(searchLower)) {
                const rect = element.getBoundingClientRect();
                const textLayerRect = textLayer.getBoundingClientRect();
                
                const highlight = document.createElement('div');
                highlight.style.position = 'absolute';
                highlight.style.left = `${rect.left - textLayerRect.left}px`;
                highlight.style.top = `${rect.top - textLayerRect.top}px`;
                highlight.style.width = `${rect.width}px`;
                highlight.style.height = `${rect.height}px`;
                highlight.style.backgroundColor = '#ffeb3b';
                highlight.style.opacity = '0.3';
                highlight.style.pointerEvents = 'none';
                highlight.style.zIndex = '10';
                highlight.style.borderRadius = '2px';
                
                textLayer.appendChild(highlight);
                highlights.push(highlight);
                results.push(element.textContent);
            }
        });

        setHighlightedElements(highlights);
        setSearchResults(results);
        setCurrentSearchIndex(0);
    };

    const clearSearch = () => {
        setSearchTerm('');
        setSearchResults([]);
        setCurrentSearchIndex(0);
        clearHighlights();
    };

    const handleSearchKeyPress = (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    };

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

            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px', gap: '10px', flexWrap: 'wrap' }}>
                <button onClick={goToPrevPage} disabled={pageNumber <= 1 || loadingPdf} style={{
                    padding: '8px 15px',
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
                {highlightedTexts.length > 0 && (
                    <button onClick={toggleHighlights} style={{
                        padding: '8px 15px',
                        backgroundColor: highlightedElements.length > 0 ? '#28a745' : '#ffc107',
                        color: 'white',
                        border: 'none',
                        borderRadius: '5px',
                        cursor: 'pointer'
                    }}>
                        {highlightedElements.length > 0 ? 'Clear Highlights' : 'Highlight Relevant Text'}
                    </button>
                )}
                <button onClick={() => setShowSearch(!showSearch)} style={{
                    padding: '8px 15px',
                    backgroundColor: showSearch ? '#6c757d' : '#17a2b8',
                    color: 'white',
                    border: 'none',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                }}>
                    <FaSearch /> Search
                </button>
            </div>

            {/* Search Bar */}
            {showSearch && (
                <div style={{ 
                    display: 'flex', 
                    justifyContent: 'center', 
                    marginBottom: '10px', 
                    gap: '10px',
                    alignItems: 'center'
                }}>
                    <div style={{ position: 'relative' }}>
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            onKeyPress={handleSearchKeyPress}
                            placeholder="Search in PDF..."
                            style={{
                                padding: '8px 35px 8px 12px',
                                border: '1px solid #ddd',
                                borderRadius: '5px',
                                width: '250px',
                                fontSize: '14px'
                            }}
                        />
                        {searchTerm && (
                            <button
                                onClick={clearSearch}
                                style={{
                                    position: 'absolute',
                                    right: '8px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    color: '#999'
                                }}
                            >
                                <FaTimes />
                            </button>
                        )}
                    </div>
                    <button onClick={performSearch} disabled={!searchTerm.trim()} style={{
                        padding: '8px 15px',
                        backgroundColor: searchTerm.trim() ? '#28a745' : '#6c757d',
                        color: 'white',
                        border: 'none',
                        borderRadius: '5px',
                        cursor: searchTerm.trim() ? 'pointer' : 'not-allowed'
                    }}>
                        Find
                    </button>
                    {searchResults.length > 0 && (
                        <span style={{ fontSize: '12px', color: '#666' }}>
                            {searchResults.length} result{searchResults.length !== 1 ? 's' : ''}
                        </span>
                    )}
                </div>
            )}

            <div style={{ border: '1px solid #ccc', overflow: 'auto', maxHeight: '500px', backgroundColor: 'white', position: 'relative' }}>
                {loadingPdf && <p style={{ textAlign: 'center', padding: '20px' }}>Loading PDF...</p>}
                {pdfError && <p style={{ color: 'red', textAlign: 'center', padding: '20px' }}>{pdfError}</p>}
                {!loadingPdf && !pdfError && fileUrl && (
                    <Document
                        file={fileUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        onLoadError={onDocumentLoadError}
                    >
                        <Page
                            pageNumber={pageNumber}
                            renderTextLayer={true}
                            renderAnnotationLayer={true}
                            width={550}
                        />
                    </Document>
                )}
            </div>


        </div>
    );
};

export default PdfHighlighter;
