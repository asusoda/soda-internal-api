import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error details for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI
      return (
        <div style={{ 
          padding: '20px', 
          color: 'red', 
          backgroundColor: '#1a1a1a',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <h2 style={{ color: '#ff6b6b', marginBottom: '20px' }}>
            Something went wrong.
          </h2>
          <p style={{ color: '#ccc', marginBottom: '20px' }}>
            The application encountered an unexpected error. Please refresh the page or contact support if the problem persists.
          </p>
          <details style={{ 
            backgroundColor: '#2a2a2a', 
            padding: '15px', 
            borderRadius: '5px',
            maxWidth: '80%',
            overflow: 'auto'
          }}>
            <summary style={{ cursor: 'pointer', marginBottom: '10px' }}>
              Error Details (Click to expand)
            </summary>
            <div style={{ marginTop: '10px' }}>
              <h4 style={{ color: '#ff6b6b' }}>Error:</h4>
              <pre style={{ 
                color: '#ff6b6b', 
                whiteSpace: 'pre-wrap',
                fontSize: '12px',
                marginBottom: '15px'
              }}>
                {this.state.error && this.state.error.toString()}
              </pre>
              <h4 style={{ color: '#ff6b6b' }}>Component Stack:</h4>
              <pre style={{ 
                color: '#ccc', 
                whiteSpace: 'pre-wrap',
                fontSize: '12px'
              }}>
                {this.state.errorInfo && this.state.errorInfo.componentStack}
              </pre>
            </div>
          </details>
          <button 
            onClick={() => window.location.reload()} 
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              backgroundColor: '#4CAF50',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
              fontSize: '16px'
            }}
          >
            Refresh Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
