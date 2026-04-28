import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function SearchPage() {
  return (
    <>
      <PageHeader
        title="Поиск"
        sub="Глобальный поиск по блогерам, брифам, интеграциям и моделям."
      />
      <EmptyState title="Заглушка" description="Реализация в T18." />
    </>
  );
}

export default SearchPage;
