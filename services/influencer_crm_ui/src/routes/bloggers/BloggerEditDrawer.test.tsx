import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { BloggerEditDrawer } from './BloggerEditDrawer';

describe('BloggerEditDrawer', () => {
  it('creates a new blogger via the form', async () => {
    let closed = false;
    renderWithProviders(
      <MemoryRouter>
        <BloggerEditDrawer
          open
          onClose={() => {
            closed = true;
          }}
        />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/handle/i), 'e2e_test_handle');
    await userEvent.click(screen.getByRole('button', { name: /сохранить/i }));
    await waitFor(() => expect(closed).toBe(true));
  });
});
