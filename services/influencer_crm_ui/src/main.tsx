import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles/globals.css';

// Mount axe-core only in dev — it's a heavy auditor and we don't want it in
// production bundles. The dynamic import keeps it out of the prod chunk graph.
if (import.meta.env.DEV) {
  void import('@axe-core/react').then(async ({ default: axe }) => {
    const React = await import('react');
    const ReactDOM = await import('react-dom');
    axe(React, ReactDOM, 1000);
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
