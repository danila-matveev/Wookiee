import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { createQueryClient } from './lib/query-client';

const client = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={client}>
      <div className="p-8 font-display text-2xl">Wookiee CRM — alive</div>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
