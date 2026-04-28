import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function IntegrationsKanbanPage() {
  return (
    <>
      <PageHeader
        title="Интеграции"
        sub="Канбан по статусам. Перетаскивайте карточки между колонками."
      />
      <EmptyState title="Заглушка" description="Реализация в T13." />
    </>
  );
}

export default IntegrationsKanbanPage;
