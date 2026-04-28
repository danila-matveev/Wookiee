import { Link } from 'react-router-dom';
import { PageHeader } from '@/layout/PageHeader';
import { Button } from '@/ui/Button';
import { EmptyState } from '@/ui/EmptyState';

export function NotFound() {
  return (
    <>
      <PageHeader title="404" sub="Страница не найдена." />
      <EmptyState
        title="Такого маршрута нет"
        description="Возможно, страница была перемещена или ещё не реализована."
        action={
          <Link to="/bloggers">
            <Button variant="primary">На главную</Button>
          </Link>
        }
      />
    </>
  );
}

export default NotFound;
