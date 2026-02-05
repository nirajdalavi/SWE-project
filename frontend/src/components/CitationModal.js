import React, { useState, useEffect } from 'react';
import { FaTimes, FaFilePdf, FaSearch, FaCopy } from 'react-icons/fa';
import PdfHighlighter from './PdfHighlighter';

const CitationModal = ({ 
    isOpen, 
    onClose, 
    citation, 
    workspaceName, 
    resumeName, 
    criterionName,
    rationale 
}) => {
    const [showPdf, setShowPdf] = useState(false);
    const [highlightedText, setHighlightedText] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isOpen && citation) {
            setLoading(true);
            extractHighlightedText();
        }
    }, [isOpen, citation, rationale]);

    const extractHighlightedText = () => {
        if (!rationale) {
            setLoading(false);
            return;
        }

        // Try to extract relevant text from the rationale
        const sentences = rationale.split(/[.!?]+/).filter(s => s.trim().length > 10);
        if (sentences.length > 0) {
            // Take the first few sentences as the highlighted text
            const relevantText = sentences.slice(0, 2).join('. ') + '.';
            setHighlightedText(relevantText);
        }
        setLoading(false);
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text).then(() => {
            console.log('Text copied to clipboard');
        });
    };

    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
            padding: '20px'
        }}>
            <div style={{
                backgroundColor: 'white',
                borderRadius: '12px',
                maxWidth: '900px',
                width: '100%',
                maxHeight: '90vh',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)'
            }}>
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '20px 24px',
                    borderBottom: '1px solid #e9ecef',
                    backgroundColor: '#f8f9fa'
                }}>
                    <div>
                        <h3 style={{ margin: 0, color: '#495057', fontSize: '18px', fontWeight: '600' }}>
                            Citation for {criterionName}
                        </h3>
                        <p style={{ margin: '4px 0 0 0', color: '#6c757d', fontSize: '14px' }}>
                            Resume: {resumeName}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none',
                            border: 'none',
                            fontSize: '20px',
                            cursor: 'pointer',
                            color: '#6c757d',
                            padding: '8px',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}
                        onMouseEnter={(e) => e.target.style.backgroundColor = '#e9ecef'}
                        onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
                    >
                        <FaTimes />
                    </button>
                </div>

                {/* Content */}
                <div style={{
                    flex: 1,
                    overflow: 'auto',
                    padding: '24px'
                }}>
                    {loading ? (
                        <div style={{ textAlign: 'center', padding: '40px' }}>
                            <div style={{ fontSize: '16px', color: '#6c757d' }}>Loading citation...</div>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                            {/* Rationale Section */}
                            <div style={{
                                backgroundColor: '#f8f9fa',
                                padding: '16px',
                                borderRadius: '8px',
                                border: '1px solid #e9ecef'
                            }}>
                                <h4 style={{ margin: '0 0 12px 0', color: '#495057', fontSize: '16px' }}>
                                    <FaSearch style={{ marginRight: '8px', color: '#0d6efd' }} />
                                    AI Rationale
                                </h4>
                                <p style={{ 
                                    margin: 0, 
                                    color: '#495057', 
                                    lineHeight: '1.6',
                                    fontSize: '14px'
                                }}>
                                    {rationale || 'No rationale available'}
                                </p>
                            </div>



                            {/* Source Document Section */}
                            <div style={{
                                backgroundColor: '#e7f3ff',
                                padding: '16px',
                                borderRadius: '8px',
                                border: '1px solid #b6d4fe'
                            }}>
                                <h4 style={{ margin: '0 0 12px 0', color: '#084298', fontSize: '16px' }}>
                                    <FaFilePdf style={{ marginRight: '8px' }} />
                                    Source Document
                                </h4>
                                <p style={{ 
                                    margin: '0 0 16px 0', 
                                    color: '#084298', 
                                    fontSize: '14px' 
                                }}>
                                    View the original resume document to see the full context.
                                </p>
                                <button
                                    onClick={() => setShowPdf(!showPdf)}
                                    style={{
                                        backgroundColor: '#0d6efd',
                                        color: 'white',
                                        border: 'none',
                                        padding: '10px 16px',
                                        borderRadius: '6px',
                                        cursor: 'pointer',
                                        fontSize: '14px',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px'
                                    }}
                                    onMouseEnter={(e) => e.target.style.backgroundColor = '#0b5ed7'}
                                    onMouseLeave={(e) => e.target.style.backgroundColor = '#0d6efd'}
                                >
                                    {showPdf ? 'Hide Document' : 'View Resume PDF'}
                                </button>
                            </div>

                            {/* PDF Viewer */}
                            {showPdf && citation?.pdf_filename ? (
                                <div style={{
                                    border: '1px solid #dee2e6',
                                    borderRadius: '8px',
                                    overflow: 'hidden'
                                }}>
                                    <PdfHighlighter
                                        workspaceName={workspaceName}
                                        fileName={`resumes/${citation.pdf_filename}`}
                                        highlightedTexts={citation?.relevant_chunks || []}
                                        onClose={() => setShowPdf(false)}
                                        initialPage={1}
                                    />
                                </div>
                            ) : showPdf && !citation?.pdf_filename ? (
                                <div style={{
                                    padding: '20px',
                                    textAlign: 'center',
                                    backgroundColor: '#f8f9fa',
                                    border: '1px solid #dee2e6',
                                    borderRadius: '8px'
                                }}>
                                    <p style={{ color: '#6c757d', margin: 0 }}>
                                        PDF file not found for this resume.
                                    </p>
                                </div>
                            ) : null}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CitationModal;
