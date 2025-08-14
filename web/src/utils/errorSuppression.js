/**
 * Utility to suppress specific console errors that are known to be harmless
 */

// List of error messages to suppress
const SUPPRESSED_ERRORS = [
  'ResizeObserver loop completed with undelivered notifications',
  'ResizeObserver loop limit exceeded',
];

// Store original console methods
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

// Enhanced console.error that filters out known harmless errors
console.error = (...args) => {
  const message = args.join(' ');
  
  // Check if this is a suppressed error
  const shouldSuppress = SUPPRESSED_ERRORS.some(suppressedError => 
    message.includes(suppressedError)
  );
  
  if (!shouldSuppress) {
    originalConsoleError.apply(console, args);
  }
};

// Enhanced console.warn for potential warnings
console.warn = (...args) => {
  const message = args.join(' ');
  
  // Check if this is a suppressed warning
  const shouldSuppress = SUPPRESSED_ERRORS.some(suppressedError => 
    message.includes(suppressedError)
  );
  
  if (!shouldSuppress) {
    originalConsoleWarn.apply(console, args);
  }
};

// Global error handler for uncaught errors
const handleGlobalError = (event) => {
  const message = event.message || event.error?.message || '';
  
  // Check if this is a suppressed error
  const shouldSuppress = SUPPRESSED_ERRORS.some(suppressedError => 
    message.includes(suppressedError)
  );
  
  if (shouldSuppress) {
    event.preventDefault();
    event.stopImmediatePropagation();
    return false;
  }
};

// Set up global error handling
if (typeof window !== 'undefined') {
  window.addEventListener('error', handleGlobalError, true);
  window.addEventListener('unhandledrejection', (event) => {
    const message = event.reason?.message || '';
    const shouldSuppress = SUPPRESSED_ERRORS.some(suppressedError => 
      message.includes(suppressedError)
    );
    
    if (shouldSuppress) {
      event.preventDefault();
    }
  });
}

export { originalConsoleError, originalConsoleWarn }; 