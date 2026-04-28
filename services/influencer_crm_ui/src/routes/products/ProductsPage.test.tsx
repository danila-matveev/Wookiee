import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { ProductsPage } from './ProductsPage';

describe('ProductsPage', () => {
  it('renders products from API', async () => {
    renderWithProviders(
      <MemoryRouter>
        <ProductsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Wendy/i)).toBeInTheDocument());
    expect(screen.getByText(/Joy/i)).toBeInTheDocument();
  });
});
