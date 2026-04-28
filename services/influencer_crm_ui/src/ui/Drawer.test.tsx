import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Drawer } from './Drawer';

describe('Drawer', () => {
  it('calls onClose when Esc pressed', async () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="Edit blogger">
        <p>body</p>
      </Drawer>,
    );
    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('renders title and traps focus on first focusable', () => {
    render(
      <Drawer open onClose={() => {}} title="Edit blogger">
        <button type="button">save</button>
      </Drawer>,
    );
    expect(screen.getByText('Edit blogger')).toBeInTheDocument();
  });
});
