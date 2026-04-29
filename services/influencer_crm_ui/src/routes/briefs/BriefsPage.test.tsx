import { screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { BriefsPage } from './BriefsPage';

describe('BriefsPage', () => {
  it('renders kanban columns and brief cards from fixtures', async () => {
    renderWithProviders(
      <MemoryRouter>
        <BriefsPage />
      </MemoryRouter>,
    );

    // Header renders.
    expect(screen.getByText('Брифы')).toBeInTheDocument();

    // All 4 columns appear.
    await waitFor(() => expect(screen.getByTestId('brief-column-draft')).toBeInTheDocument());
    expect(screen.getByTestId('brief-column-on_review')).toBeInTheDocument();
    expect(screen.getByTestId('brief-column-signed')).toBeInTheDocument();
    expect(screen.getByTestId('brief-column-completed')).toBeInTheDocument();

    // First fixture (id=101, draft, "_anna.blog") lands in the Черновик column.
    const draftCol = screen.getByTestId('brief-column-draft');
    await waitFor(() => expect(within(draftCol).getByTestId('brief-card-101')).toBeInTheDocument());
    expect(within(draftCol).getByText(/_anna\.blog/i)).toBeInTheDocument();

    // Status filter pill labels are present (one per status, plus Все).
    expect(screen.getByRole('button', { name: /Все/ })).toBeInTheDocument();
  });
});
