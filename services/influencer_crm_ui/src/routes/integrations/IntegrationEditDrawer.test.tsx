import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { IntegrationEditDrawer } from './IntegrationEditDrawer';

describe('IntegrationEditDrawer', () => {
  it('loads detail and renders form for edit mode', async () => {
    renderWithProviders(
      <MemoryRouter>
        <IntegrationEditDrawer open id={1} onClose={() => {}} />
      </MemoryRouter>,
    );
    // Wait for detail-fetch to populate the form (publish_date prefill from MSW fixture).
    await waitFor(() => {
      const dateInput = screen.getByLabelText(/дата публикации/i) as HTMLInputElement;
      expect(dateInput.value).toBe('2026-05-12');
    });
    // Static fields rendered immediately (Section structure).
    expect(screen.getByLabelText(/маркетплейс/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^id блогера/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^id маркетолога/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^стадия/i)).toBeInTheDocument();
    expect(screen.getByText(/подменные артикулы/i)).toBeInTheDocument();
  });
});
