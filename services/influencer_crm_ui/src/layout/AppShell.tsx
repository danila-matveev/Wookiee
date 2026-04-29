import { Outlet } from 'react-router-dom';
import { Sidebar } from '@/layout/Sidebar';
import { TopBar } from '@/layout/TopBar';

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1600px] px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppShell;
