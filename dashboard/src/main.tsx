import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './index.css';
import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router';
import { App } from './app';
import { ConfirmProvider } from './components/confirm';
import { TooltipProvider } from './components/tooltip';
import { ApiError } from './lib/api';
import { startErrorReports } from './lib/error-report';
import { createQueryClient } from './lib/query-client';
import { applyTheme, storedTheme } from './lib/theme';

applyTheme(storedTheme());
startErrorReports();

const queryClient = createQueryClient();

queryClient.getQueryCache().subscribe((event) => {
  const error = event.query.state.error;
  if (error instanceof ApiError && error.status === 401 && location.pathname !== '/login' && !location.pathname.startsWith('/store/')) location.assign('/login');
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <ConfirmProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </ConfirmProvider>
    </TooltipProvider>
  </StrictMode>,
);
