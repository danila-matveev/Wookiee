import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { CalendarPage } from './CalendarPage';

describe('CalendarPage', () => {
  it('renders month grid with 42 day cells', async () => {
    renderWithProviders(
      <MemoryRouter>
        <CalendarPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Календарь публикаций')).toBeInTheDocument();

    await waitFor(() => expect(screen.getAllByRole('gridcell').length).toBeGreaterThanOrEqual(42));
  });
});
