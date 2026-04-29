import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { SearchPage } from './SearchPage';

describe('SearchPage', () => {
  it('shows the empty prompt when no q is set', () => {
    renderWithProviders(
      <MemoryRouter initialEntries={['/search']}>
        <SearchPage />
      </MemoryRouter>,
    );
    // Empty state EmptyState uses an exact title; the sub-line on PageHeader
    // also mentions the phrase, so we match the EmptyState description specifically.
    expect(screen.getByText(/Минимум 2 символа/i)).toBeInTheDocument();
  });

  it('renders blogger and integration results from MSW for ?q=anna', async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={['/search?q=anna']}>
        <SearchPage />
      </MemoryRouter>,
    );

    // Sub-line echoes the query.
    expect(screen.getByText(/по запросу «anna»/i)).toBeInTheDocument();

    // Blogger card from fixture (Anna Search / _anna.blog).
    await waitFor(() => expect(screen.getByTestId('search-result-blogger-11')).toBeInTheDocument());
    expect(screen.getByText(/Anna Search/i)).toBeInTheDocument();

    // Integration card from fixture (id 91, blogger #11).
    expect(screen.getByTestId('search-result-integration-91')).toBeInTheDocument();
    expect(screen.getByText(/Блогер #11/)).toBeInTheDocument();

    // Tabs render with counts.
    expect(screen.getByRole('tab', { name: /Все/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Блогеры/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Интеграции/ })).toBeInTheDocument();
  });
});
