import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function BloggersPage() {
  return (
    <>
      <PageHeader
        title="Блогеры"
        sub="Все блогеры в работе. Клик по строке — детали и история интеграций."
      />
      <EmptyState title="Заглушка" description="Реализация в T10." />
    </>
  );
}

export default BloggersPage;
