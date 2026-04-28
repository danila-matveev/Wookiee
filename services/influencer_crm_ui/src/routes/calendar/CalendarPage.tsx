import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function CalendarPage() {
  return (
    <>
      <PageHeader title="Календарь" sub="План публикаций и съёмок по неделям." />
      <EmptyState title="Заглушка" description="Реализация в T14." />
    </>
  );
}

export default CalendarPage;
