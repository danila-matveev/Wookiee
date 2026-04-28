import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function BriefsPage() {
  return (
    <>
      <PageHeader title="Брифы" sub="Шаблоны и активные брифы для блогеров." />
      <EmptyState title="Заглушка" description="Реализация в T15." />
    </>
  );
}

export default BriefsPage;
