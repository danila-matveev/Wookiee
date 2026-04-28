import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useId } from 'react';
import { type SubmitHandler, type UseFormReturn, useForm } from 'react-hook-form';
import { z } from 'zod';
import type {
  AdFormat,
  Channel,
  IntegrationDetailOut,
  IntegrationInput,
  Marketplace,
  Outcome,
  Stage,
} from '@/api/integrations';
import { STAGES } from '@/api/integrations';
import { useIntegration, useUpsertIntegration } from '@/hooks/use-integrations';
import { Button } from '@/ui/Button';
import { Drawer } from '@/ui/Drawer';
import { EmptyState } from '@/ui/EmptyState';
import { Input } from '@/ui/Input';
import { Select } from '@/ui/Select';
import { Textarea } from '@/ui/Textarea';

const STAGE_LABELS: Record<Stage, string> = {
  lead: 'Лид',
  negotiation: 'Переговоры',
  agreed: 'Согласовано',
  content_received: 'Контент получен',
  content_approved: 'Контент утверждён',
  scheduled: 'Запланировано',
  published: 'Опубликовано',
  paid: 'Оплачено',
  done: 'Готово',
  rejected: 'Отклонено',
};

const CHANNEL_OPTIONS: { value: Channel; label: string }[] = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'vk', label: 'VK' },
  { value: 'rutube', label: 'RuTube' },
];

const AD_FORMAT_OPTIONS: { value: AdFormat; label: string }[] = [
  { value: 'story', label: 'Сторис' },
  { value: 'short_video', label: 'Короткое видео (Reels/Shorts)' },
  { value: 'long_video', label: 'Длинное видео' },
  { value: 'long_post', label: 'Длинный пост' },
  { value: 'image_post', label: 'Пост с фото' },
  { value: 'integration', label: 'Нативная интеграция' },
  { value: 'live_stream', label: 'Прямой эфир' },
];

const MARKETPLACE_OPTIONS: { value: Marketplace; label: string }[] = [
  { value: 'wb', label: 'WB' },
  { value: 'ozon', label: 'OZON' },
  { value: 'both', label: 'WB + OZON' },
];

const OUTCOME_OPTIONS: { value: '' | Outcome; label: string }[] = [
  { value: '', label: '—' },
  { value: 'delivered', label: 'Выполнено' },
  { value: 'cancelled', label: 'Отменено' },
  { value: 'no_show', label: 'Не вышло' },
  { value: 'failed_compliance', label: 'Compliance fail' },
];

// Helpers — reused decimal/int validators following the BloggerEditDrawer playbook.
// Decimal fields stay strings end-to-end (Decimal precision rule); empty → null.
const optionalDecimal = z
  .string()
  .trim()
  .optional()
  .superRefine((v, ctx) => {
    if (v && v.length > 0 && !/^\d+(\.\d+)?$/.test(v)) {
      ctx.addIssue({ code: 'custom', message: 'Только цифры (например 12345.67)' });
    }
  })
  .transform((v) => (v && v.length > 0 ? v : null));

const requiredIntId = z
  .string()
  .trim()
  .min(1, 'Обязательное поле')
  .superRefine((v, ctx) => {
    if (!/^\d+$/.test(v)) {
      ctx.addIssue({ code: 'custom', message: 'Должно быть целое число' });
    }
  })
  .transform((v) => Number(v));

const optionalInt = z
  .string()
  .trim()
  .optional()
  .superRefine((v, ctx) => {
    if (v && v.length > 0 && !/^\d+$/.test(v)) {
      ctx.addIssue({ code: 'custom', message: 'Должно быть целое число' });
    }
  })
  .transform((v) => (v && v.length > 0 ? Number(v) : null));

const optionalString = z
  .string()
  .trim()
  .optional()
  .transform((v) => (v && v.length > 0 ? v : null));

const formSchema = z.object({
  blogger_id: requiredIntId,
  marketer_id: requiredIntId,
  publish_date: z.string().min(1, 'Обязательное поле'),
  channel: z.enum(['instagram', 'telegram', 'tiktok', 'youtube', 'vk', 'rutube']),
  ad_format: z.enum([
    'story',
    'short_video',
    'long_video',
    'long_post',
    'image_post',
    'integration',
    'live_stream',
  ]),
  marketplace: z.enum(['wb', 'ozon', 'both']),
  stage: z.enum(STAGES),
  outcome: z
    .union([z.enum(['delivered', 'cancelled', 'no_show', 'failed_compliance']), z.literal('')])
    .transform((v) => (v === '' ? null : v)),
  is_barter: z.boolean(),
  cost_placement: optionalDecimal,
  cost_delivery: optionalDecimal,
  cost_goods: optionalDecimal,
  erid: optionalString,
  fact_views: optionalInt,
  fact_orders: optionalInt,
  fact_revenue: optionalDecimal,
  notes: optionalString,
});

type FormInput = z.input<typeof formSchema>;
type FormOutput = z.output<typeof formSchema>;

interface IntegrationEditDrawerProps {
  open: boolean;
  onClose: () => void;
  /** When provided AND > 0, drawer opens in edit mode. Otherwise create mode. */
  id?: number;
}

function defaultsFromDetail(detail?: IntegrationDetailOut): FormInput {
  return {
    blogger_id: detail?.blogger_id != null ? String(detail.blogger_id) : '',
    marketer_id: detail?.marketer_id != null ? String(detail.marketer_id) : '',
    publish_date: detail?.publish_date ?? '',
    channel: detail?.channel ?? 'instagram',
    ad_format: detail?.ad_format ?? 'story',
    marketplace: detail?.marketplace ?? 'wb',
    stage: detail?.stage ?? 'lead',
    outcome: detail?.outcome ?? '',
    is_barter: detail?.is_barter ?? false,
    cost_placement: detail?.cost_placement ?? '',
    cost_delivery: detail?.cost_delivery ?? '',
    cost_goods: detail?.cost_goods ?? '',
    erid: detail?.erid ?? '',
    fact_views: detail?.fact_views != null ? String(detail.fact_views) : '',
    fact_orders: detail?.fact_orders != null ? String(detail.fact_orders) : '',
    fact_revenue: detail?.fact_revenue ?? '',
    notes: detail?.notes ?? '',
  };
}

export function IntegrationEditDrawer({ open, onClose, id }: IntegrationEditDrawerProps) {
  const isEdit = id !== undefined && id > 0;
  const detailQuery = useIntegration(isEdit ? id : undefined);
  const detail = isEdit ? detailQuery.data : undefined;

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultsFromDetail(detail),
  });

  // Sync form on open / detail change. Reset only when drawer opens or a *different*
  // integration is loaded — same pattern as BloggerEditDrawer.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger
  useEffect(() => {
    if (open) {
      form.reset(defaultsFromDetail(detail));
    }
  }, [open, detail?.id, detail?.updated_at]);

  const upsert = useUpsertIntegration();

  const title = isEdit
    ? `Интеграция #${id}${detail?.blogger_handle ? ` — ${detail.blogger_handle}` : ''}`
    : 'Новая интеграция';

  const onSubmit: SubmitHandler<FormOutput> = async (values) => {
    // The form schema produces a fully-validated payload; we narrow to the BFF write shape.
    // For PATCH (edit), all keys are optional but we send the full set since RHF defaults
    // already mirror the loaded detail — no diffing needed.
    const body: IntegrationInput = {
      blogger_id: values.blogger_id,
      marketer_id: values.marketer_id,
      publish_date: values.publish_date,
      channel: values.channel,
      ad_format: values.ad_format,
      marketplace: values.marketplace,
      stage: values.stage,
      outcome: values.outcome,
      is_barter: values.is_barter,
      cost_placement: values.cost_placement,
      cost_delivery: values.cost_delivery,
      cost_goods: values.cost_goods,
      erid: values.erid,
      fact_views: values.fact_views,
      fact_orders: values.fact_orders,
      fact_revenue: values.fact_revenue,
      notes: values.notes,
    };
    await upsert.mutateAsync({ id: isEdit ? id : undefined, body });
    onClose();
  };

  // Derived total_cost (read-only display) — sum the three cost components when present.
  const watched = form.watch();
  const computedTotal = (() => {
    const parts = [watched.cost_placement, watched.cost_delivery, watched.cost_goods]
      .map((v) => (v && /^\d+(\.\d+)?$/.test(v) ? Number(v) : 0))
      .reduce((a, b) => a + b, 0);
    return parts > 0
      ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(parts)
      : '0';
  })();

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
      width="max-w-3xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={upsert.isPending}>
            Отмена
          </Button>
          <Button
            variant="primary"
            loading={upsert.isPending}
            onClick={form.handleSubmit(onSubmit)}
          >
            Сохранить
          </Button>
        </>
      }
    >
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6">
        <BasicsSection form={form} />
        <CostsSection form={form} totalDisplay={computedTotal} />
        <ComplianceSection form={form} />
        <FactSection form={form} />
        <SubstitutesSection detail={detail} isEdit={isEdit} />
        {upsert.error && (
          <p className="text-sm text-danger">
            Не удалось сохранить:{' '}
            {upsert.error instanceof Error ? upsert.error.message : 'неизвестная ошибка'}
          </p>
        )}
        {/* Hidden submit so Enter inside a field triggers handleSubmit */}
        <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
      </form>
    </Drawer>
  );
}

interface SectionProps {
  form: UseFormReturn<FormInput, unknown, FormOutput>;
}

function BasicsSection({ form }: SectionProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const bloggerId = useId();
  const marketerId = useId();
  const publishDateId = useId();
  const channelId = useId();
  const adFormatId = useId();
  const marketplaceId = useId();
  const stageId = useId();
  const outcomeId = useId();
  const barterId = useId();

  return (
    <Section title="Основное">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="ID блогера*" htmlFor={bloggerId} error={errors.blogger_id?.message}>
          <Input
            id={bloggerId}
            inputMode="numeric"
            placeholder="например, 11"
            {...register('blogger_id')}
          />
        </Field>

        <Field label="ID маркетолога*" htmlFor={marketerId} error={errors.marketer_id?.message}>
          <Input
            id={marketerId}
            inputMode="numeric"
            placeholder="например, 7"
            {...register('marketer_id')}
          />
        </Field>

        <Field
          label="Дата публикации*"
          htmlFor={publishDateId}
          error={errors.publish_date?.message}
        >
          <Input id={publishDateId} type="date" {...register('publish_date')} />
        </Field>

        <Field label="Маркетплейс*" htmlFor={marketplaceId} error={errors.marketplace?.message}>
          <Select id={marketplaceId} {...register('marketplace')}>
            {MARKETPLACE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Канал*" htmlFor={channelId} error={errors.channel?.message}>
          <Select id={channelId} {...register('channel')}>
            {CHANNEL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Формат*" htmlFor={adFormatId} error={errors.ad_format?.message}>
          <Select id={adFormatId} {...register('ad_format')}>
            {AD_FORMAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Стадия*" htmlFor={stageId} error={errors.stage?.message}>
          <Select id={stageId} {...register('stage')}>
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {STAGE_LABELS[s]}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Исход" htmlFor={outcomeId} error={errors.outcome?.message}>
          <Select id={outcomeId} {...register('outcome')}>
            {OUTCOME_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>

        <div className="flex items-center gap-2 sm:col-span-2">
          <input
            id={barterId}
            type="checkbox"
            className="size-4 rounded border-border"
            {...register('is_barter')}
          />
          <label htmlFor={barterId} className="text-sm text-fg">
            Бартер (без денежной оплаты)
          </label>
        </div>
      </div>
    </Section>
  );
}

function CostsSection({ form, totalDisplay }: SectionProps & { totalDisplay: string }) {
  const {
    register,
    formState: { errors },
  } = form;
  const placementId = useId();
  const deliveryId = useId();
  const goodsId = useId();
  const totalId = useId();

  return (
    <Section
      title="Стоимость"
      hint="Денежные поля — строки. total_cost рассчитывается на стороне БД (generated column), здесь — локальный предпросмотр."
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Размещение, ₽" htmlFor={placementId} error={errors.cost_placement?.message}>
          <Input
            id={placementId}
            inputMode="decimal"
            placeholder="0"
            {...register('cost_placement')}
          />
        </Field>

        <Field label="Доставка, ₽" htmlFor={deliveryId} error={errors.cost_delivery?.message}>
          <Input
            id={deliveryId}
            inputMode="decimal"
            placeholder="0"
            {...register('cost_delivery')}
          />
        </Field>

        <Field label="Товар, ₽" htmlFor={goodsId} error={errors.cost_goods?.message}>
          <Input id={goodsId} inputMode="decimal" placeholder="0" {...register('cost_goods')} />
        </Field>

        <Field label="Итого, ₽ (auto)" htmlFor={totalId}>
          <Input id={totalId} value={totalDisplay} readOnly className="bg-muted/40" />
        </Field>
      </div>
    </Section>
  );
}

function ComplianceSection({ form }: SectionProps) {
  const {
    register,
    formState: { errors },
    watch,
  } = form;
  const eridId = useId();
  const notesId = useId();
  const stage = watch('stage');
  const eridRequiredHint = stage === 'published';

  return (
    <Section title="Compliance">
      <div className="grid grid-cols-1 gap-4">
        <Field
          label={`ERID${eridRequiredHint ? ' (обязательно для published)' : ''}`}
          htmlFor={eridId}
          error={errors.erid?.message}
        >
          <Input id={eridId} placeholder="напр. 2VtzqwYjJjA" {...register('erid')} />
        </Field>

        <Field label="Заметки" htmlFor={notesId} error={errors.notes?.message}>
          <Textarea
            id={notesId}
            rows={3}
            placeholder="ТЗ, договорённости, ссылка на пост..."
            {...register('notes')}
          />
        </Field>
      </div>
    </Section>
  );
}

function FactSection({ form }: SectionProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const viewsId = useId();
  const ordersId = useId();
  const revenueId = useId();

  return (
    <Section
      title="Факт"
      hint="Финальные показатели. Снимки метрик во времени — отдельная таблица crm.integration_metrics_snapshots, форма для них появится в T19/T20."
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Просмотры" htmlFor={viewsId} error={errors.fact_views?.message}>
          <Input id={viewsId} inputMode="numeric" placeholder="0" {...register('fact_views')} />
        </Field>

        <Field label="Заказы, шт" htmlFor={ordersId} error={errors.fact_orders?.message}>
          <Input id={ordersId} inputMode="numeric" placeholder="0" {...register('fact_orders')} />
        </Field>

        <Field label="Выручка, ₽" htmlFor={revenueId} error={errors.fact_revenue?.message}>
          <Input id={revenueId} inputMode="decimal" placeholder="0" {...register('fact_revenue')} />
        </Field>
      </div>
    </Section>
  );
}

function SubstitutesSection({
  detail,
  isEdit,
}: {
  detail?: IntegrationDetailOut;
  isEdit: boolean;
}) {
  if (!isEdit) {
    return (
      <Section title="Подменные артикулы">
        <EmptyState
          title="Сначала сохрани интеграцию"
          description="Подменные артикулы можно будет привязать после создания записи."
        />
      </Section>
    );
  }

  if (!detail) {
    return (
      <Section title="Подменные артикулы">
        <p className="text-sm text-muted-fg">Загрузка...</p>
      </Section>
    );
  }

  if (detail.substitutes.length === 0) {
    return (
      <Section title="Подменные артикулы">
        <EmptyState
          title="Нет подменных артикулов"
          description="CRUD junction-таблицы будет добавлен в T19+ через отдельный endpoint."
        />
      </Section>
    );
  }

  return (
    <Section title="Подменные артикулы">
      <ul className="flex flex-col gap-2">
        {detail.substitutes.map((s) => (
          <li
            key={s.substitute_article_id}
            className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm"
          >
            <span>
              <span className="font-medium">{s.code}</span>
              {s.artikul_id != null && (
                <span className="ml-2 text-muted-fg">(artikul #{s.artikul_id})</span>
              )}
            </span>
            {s.tracking_url && (
              <a
                href={s.tracking_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary hover:text-primary-hover"
              >
                Открыть
              </a>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <header>
        <h3 className="font-display text-sm font-semibold text-fg">{title}</h3>
        {hint && <p className="mt-1 text-xs text-muted-fg">{hint}</p>}
      </header>
      {children}
    </section>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-xs font-medium text-muted-fg">
        {label}
      </label>
      {children}
      {error && <p className="text-xs text-danger mt-1">{error}</p>}
    </div>
  );
}

export default IntegrationEditDrawer;
