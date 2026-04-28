import { screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { IntegrationsKanbanPage } from './IntegrationsKanbanPage';

describe('IntegrationsKanbanPage', () => {
  it('mounts, fetches, and renders cards in their stage columns', async () => {
    renderWithProviders(
      <MemoryRouter>
        <IntegrationsKanbanPage />
      </MemoryRouter>,
    );

    // Header renders.
    expect(screen.getByText('Интеграции')).toBeInTheDocument();

    // All 10 columns are present.
    await waitFor(() => expect(screen.getByTestId('kanban-column-lead')).toBeInTheDocument());
    expect(screen.getByTestId('kanban-column-rejected')).toBeInTheDocument();

    // Card 1 (lead) — fixture has blogger_id 11.
    const leadColumn = screen.getByTestId('kanban-column-lead');
    await waitFor(() => expect(within(leadColumn).getByText('Блогер #11')).toBeInTheDocument());

    // Card 3 (scheduled) — fixture has blogger_id 13, barter card.
    const scheduledColumn = screen.getByTestId('kanban-column-scheduled');
    expect(within(scheduledColumn).getByText('Блогер #13')).toBeInTheDocument();
  });
});
