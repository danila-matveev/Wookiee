import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function SlicesPage() {
  return (
    <>
      <PageHeader title="Срезы" sub="Сохранённые срезы аудитории и блогеров." />
      <EmptyState title="Заглушка" description="Реализация в T17." />
    </>
  );
}

export default SlicesPage;
