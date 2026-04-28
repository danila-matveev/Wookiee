import { PageHeader } from '@/layout/PageHeader';
import { EmptyState } from '@/ui/EmptyState';

export function ProductsPage() {
  return (
    <>
      <PageHeader
        title="Продукты"
        sub="Каталог моделей Wookiee — связь с интеграциями и аналитикой."
      />
      <EmptyState title="Заглушка" description="Реализация в T16." />
    </>
  );
}

export default ProductsPage;
