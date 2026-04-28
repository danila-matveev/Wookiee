import { Bell, Search } from 'lucide-react';
import { type FormEvent, useId, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input } from '@/ui/Input';

export function TopBar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const inputId = useId();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-card/80 backdrop-blur">
      <div className="flex items-center justify-between gap-4 px-8 py-3">
        <search className="max-w-md flex-1">
          <form onSubmit={handleSubmit}>
            <label htmlFor={inputId} className="relative block">
              <span className="sr-only">Поиск</span>
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-fg"
              />
              <Input
                id={inputId}
                type="search"
                placeholder="Поиск по блогерам, брифам, моделям…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
              />
            </label>
          </form>
        </search>

        <button
          type="button"
          aria-label="Уведомления"
          className="flex size-9 cursor-pointer items-center justify-center rounded-md text-muted-fg hover:bg-primary-light hover:text-fg"
        >
          <Bell className="size-4" />
        </button>
      </div>
    </header>
  );
}

export default TopBar;
