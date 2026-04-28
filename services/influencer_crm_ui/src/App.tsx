import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { RouterProvider } from 'react-router-dom';
import { createQueryClient } from './lib/query-client';
import { router } from './routes/router';

const client = createQueryClient();

export function App() {
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
