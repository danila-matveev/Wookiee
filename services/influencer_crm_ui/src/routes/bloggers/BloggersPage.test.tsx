import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { BloggersPage } from './BloggersPage';

describe('BloggersPage', () => {
  it('renders bloggers from API', async () => {
    renderWithProviders(
      <MemoryRouter>
        <BloggersPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/_anna.blog/)).toBeInTheDocument());
  });
});
