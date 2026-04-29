import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { SlicesPage } from './SlicesPage';

describe('SlicesPage', () => {
  it('renders KPI cards and result table from MSW data', async () => {
    renderWithProviders(
      <MemoryRouter>
        <SlicesPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Срезы интеграций')).toBeInTheDocument();

    // KPI cards present after mount.
    await waitFor(() => expect(screen.getByText(/^Расход$/)).toBeInTheDocument());
    expect(screen.getByText(/^Просмотры$/)).toBeInTheDocument();
    expect(screen.getByText(/^Заказы$/)).toBeInTheDocument();
    expect(screen.getByText('ROMI')).toBeInTheDocument();

    // Result table renders after data lands.
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());

    // First row from fixture should appear (id 1 → blogger 11).
    expect(screen.getByText('Блогер #11')).toBeInTheDocument();
  });
});
