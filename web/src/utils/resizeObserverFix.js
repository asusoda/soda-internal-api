import React from 'react';

/**
 * Utility to handle ResizeObserver loop errors
 * These errors are typically harmless but can be noisy in the console
 */

// Debounce function to prevent excessive resize events
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

// Safe ResizeObserver wrapper
export class SafeResizeObserver extends ResizeObserver {
  constructor(callback) {
    const safeCallback = (entries, observer) => {
      try {
        // Use requestAnimationFrame to avoid layout thrashing
        requestAnimationFrame(() => {
          callback(entries, observer);
        });
      } catch (error) {
        // Suppress ResizeObserver loop errors
        if (!error.message.includes('ResizeObserver loop completed')) {
          console.error('ResizeObserver error:', error);
        }
      }
    };

    super(safeCallback);
  }
}

// Hook for safe resize observation
export const useSafeResizeObserver = (callback, element) => {
  const callbackRef = React.useRef(callback);
  callbackRef.current = callback;

  React.useEffect(() => {
    if (!element) return;

    const observer = new SafeResizeObserver((entries) => {
      callbackRef.current(entries);
    });

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [element]);
};

// Error boundary for ResizeObserver errors
export class ResizeObserverErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error) {
    // Check if it's a ResizeObserver error
    if (error.message && error.message.includes('ResizeObserver')) {
      return { hasError: false }; // Don't treat as error
    }
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Only log non-ResizeObserver errors
    if (!error.message || !error.message.includes('ResizeObserver')) {
      console.error('Component error:', error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <div>Something went wrong.</div>;
    }

    return this.props.children;
  }
} 