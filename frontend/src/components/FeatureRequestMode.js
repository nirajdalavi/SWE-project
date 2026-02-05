import React, { useState } from 'react';
import { FaPlus, FaPaperPlane, FaCheckCircle } from 'react-icons/fa';
import { submitFeatureRequest } from '../services/api';
import './FeatureRequestMode.css';

const FeatureRequestMode = () => {
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        priority: 'medium',
        category: 'general',
        email: ''
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isSubmitted, setIsSubmitted] = useState(false);
    const [error, setError] = useState('');

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsSubmitting(true);
        setError('');

        try {
            const response = await submitFeatureRequest(formData);
            setIsSubmitted(true);
            setFormData({
                title: '',
                description: '',
                priority: 'medium',
                category: 'general',
                email: ''
            });
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to submit feature request');
        } finally {
            setIsSubmitting(false);
        }
    };

    if (isSubmitted) {
        return (
            <div className="feature-request-success">
                <div className="success-icon">
                    <FaCheckCircle />
                </div>
                <h2>Feature Request Submitted!</h2>
                <p>Thank you for your feedback. We'll review your request and get back to you soon.</p>
                <button 
                    className="submit-another-btn"
                    onClick={() => setIsSubmitted(false)}
                >
                    Submit Another Request
                </button>
            </div>
        );
    }

    return (
        <div className="feature-request-container">
            <div className="feature-request-header">
                <div className="header-icon">
                    <FaPlus />
                </div>
                <div className="header-text">
                    <h1>Request Feature</h1>
                    <p>Help us improve Aqeed.ai by suggesting new features or improvements</p>
                </div>
            </div>

            <div className="feature-request-form-container">
                <form onSubmit={handleSubmit} className="feature-request-form">
                    <div className="form-group">
                        <label htmlFor="title">Feature Title *</label>
                        <input
                            type="text"
                            id="title"
                            name="title"
                            value={formData.title}
                            onChange={handleInputChange}
                            placeholder="e.g., Dark mode for mobile app"
                            required
                            className="form-input"
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="description">Description *</label>
                        <textarea
                            id="description"
                            name="description"
                            value={formData.description}
                            onChange={handleInputChange}
                            placeholder="Please describe the feature in detail. What problem does it solve? How would it work?"
                            required
                            rows="5"
                            className="form-textarea"
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="priority">Priority</label>
                            <select
                                id="priority"
                                name="priority"
                                value={formData.priority}
                                onChange={handleInputChange}
                                className="form-select"
                            >
                                <option value="low">Low - Nice to have</option>
                                <option value="medium">Medium - Important</option>
                                <option value="high">High - Critical</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label htmlFor="category">Category</label>
                            <select
                                id="category"
                                name="category"
                                value={formData.category}
                                onChange={handleInputChange}
                                className="form-select"
                            >
                                <option value="general">General</option>
                                <option value="ui-ux">UI/UX</option>
                                <option value="functionality">Functionality</option>
                                <option value="performance">Performance</option>
                                <option value="integration">Integration</option>
                                <option value="reporting">Reporting</option>
                                <option value="other">Other</option>
                            </select>
                        </div>
                    </div>

                    <div className="form-group">
                        <label htmlFor="email">Your Email (Optional)</label>
                        <input
                            type="email"
                            id="email"
                            name="email"
                            value={formData.email}
                            onChange={handleInputChange}
                            placeholder="your.email@example.com"
                            className="form-input"
                        />
                        <small>We'll notify you when your request is reviewed</small>
                    </div>

                    {error && (
                        <div className="error-message">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="evaluate-button"
                    >
                        {isSubmitting ? (
                            <>
                                <span className="spinner" style={{ marginRight: '8px' }}></span>
                                Submitting...
                            </>
                        ) : (
                            <>
                                <span className="evaluate-icon">▶</span>
                                Submit Request
                            </>
                        )}
                    </button>
                </form>
            </div>

            <div className="feature-request-info">
                <h3>What happens next?</h3>
                <div className="info-steps">
                    <div className="info-step">
                        <div className="step-number">1</div>
                        <div className="step-content">
                            <h4>Review</h4>
                            <p>Our team will review your request within 48 hours</p>
                        </div>
                    </div>
                    <div className="info-step">
                        <div className="step-number">2</div>
                        <div className="step-content">
                            <h4>Evaluation</h4>
                            <p>We'll assess feasibility and impact on our roadmap</p>
                        </div>
                    </div>
                    <div className="info-step">
                        <div className="step-number">3</div>
                        <div className="step-content">
                            <h4>Update</h4>
                            <p>You'll receive an email with our decision and timeline</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FeatureRequestMode;
