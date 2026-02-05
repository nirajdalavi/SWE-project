// frontend/src/components/MetricsChart.js
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getMetrics } from '../services/api';
import Chart from 'chart.js/auto';
import 'chartjs-adapter-date-fns'; // Ensure this is imported for time scale

function MetricsChart({ workspaceName }) {
  const [metricsData, setMetricsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getMetrics(workspaceName);
      setMetricsData(res.data.metrics || []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch metrics.'
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceName]);

  useEffect(() => {
    if (workspaceName) {
      fetchMetrics();
    } else {
      setMetricsData(null);
    }
  }, [workspaceName, fetchMetrics]);

  useEffect(() => {
    if (metricsData && metricsData.length > 0 && chartRef.current) {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }

      const qaData = metricsData
        .filter(m => m.mode === "Ask a question")
        .map(m => ({ x: new Date(m.timestamp), y: m.response_time }));

      const scoreData = metricsData
        .filter(m => m.mode === "Score contracts")
        .map(m => ({ x: new Date(m.timestamp), y: m.response_time }));

      const resumeScoreData = metricsData
        .filter(m => m.mode === "Score resumes")
        .map(m => ({ x: new Date(m.timestamp), y: m.response_time }));

      const vendorData = metricsData
        .filter(m => m.mode === "Vendor recommendations")
        .map(m => ({ x: new Date(m.timestamp), y: m.response_time }));

      chartInstance.current = new Chart(chartRef.current, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Score contracts',
              data: scoreData,
              borderColor: 'rgba(54, 162, 235, 1)',
              backgroundColor: 'rgba(54, 162, 235, 0.2)',
              tension: 0.1,
              fill: false,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointStyle: 'circle',
            },
            {
              label: 'Ask a question',
              data: qaData,
              borderColor: 'rgba(255, 159, 64, 1)',
              backgroundColor: 'rgba(255, 159, 64, 0.2)',
              tension: 0.1,
              fill: false,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointStyle: 'circle',
            },
            {
              label: 'Score resumes',
              data: resumeScoreData,
              borderColor: 'rgba(75, 192, 192, 1)',
              backgroundColor: 'rgba(75, 192, 192, 0.2)',
              tension: 0.1,
              fill: false,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointStyle: 'circle',
            },
            {
              label: 'Vendor recommendations',
              data: vendorData,
              borderColor: 'rgba(153, 102, 255, 1)',
              backgroundColor: 'rgba(153, 102, 255, 0.2)',
              tension: 0.1,
              fill: false,
              pointRadius: 5,
              pointHoverRadius: 7,
              pointStyle: 'circle',
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              type: 'time',
              time: {
                unit: 'minute',
                tooltipFormat: 'MMM d, h:mm:ss a',
                displayFormats: {
                    minute: 'h:mm a',
                    hour: 'MMM d h:mm a',
                    day: 'MMM d'
                },
              },
              title: {
                display: true,
                text: 'Time',
              },
              grid: {
                display: true,
                drawBorder: true,
                drawOnChartArea: true,
                drawTicks: true,
              }
            },
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Response Time (s)',
              },
              grid: {
                display: true,
                drawBorder: true,
                drawOnChartArea: true,
                drawTicks: true,
              }
            },
          },
          plugins: {
            title: {
              display: true,
              text: 'Response Time Over Time',
            },
            legend: {
              display: true,
              position: 'bottom',
              labels: {
                usePointStyle: true,
              }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                    label: function(context) {
                        return `${context.dataset.label}: ${context.parsed.y}s`;
                    }
                }
            }
          },
          elements: {
            point: {
                radius: 5,
                hoverRadius: 7,
            },
          },
        },
      });
    }
  }, [metricsData]);

  const overallAvgResponseTime = metricsData && metricsData.length > 0
    ? (metricsData.reduce((sum, m) => sum + m.response_time, 0) / metricsData.length).toFixed(2)
    : 'N/A';

  return (
    <div className="metrics-chart-card card"> {/* Added card class */}
      <div className="overall-response-time"> {/* NEW CLASS */}
          <h3 className="section-title">Response Time</h3> {/* Applied section-title */}
          <p>{overallAvgResponseTime} seconds</p> {/* Styled p */}
      </div>

      <h3 className="card-title">Response Time Over Time</h3> {/* Applied card-title */}
      {loading && <p className="small-text">Loading metrics...</p>} {/* Applied small-text */}
      {error && <p className="error-message">Error: {error}</p>} {/* Applied error-message */}

      {metricsData && metricsData.length > 0 ? (
        <div style={{ position: 'relative', height: '300px', width: '100%' }}>
          <canvas ref={chartRef}></canvas>
        </div>
      ) : (
        !loading && !error && <p className="small-text">No metrics available for this workspace. Ask questions or score contracts to generate metrics!</p> /* Applied small-text */
      )}
      <button onClick={fetchMetrics} disabled={loading} className="button secondary" style={{ marginTop: '10px' }}>Refresh Metrics</button> {/* Applied button secondary class */}
    </div>
  );
}

export default MetricsChart;