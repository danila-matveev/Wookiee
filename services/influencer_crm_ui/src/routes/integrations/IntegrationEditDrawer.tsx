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
  переговоры: 'Переговоры',
  согласовано: 'Согласовано',
  отправка_комплекта: 'Отправка комплекта',
  контент: 'Контент',
  запланировано: 'Запланировано',
  аналитика: 'Аналитика',
  завершено: 'Завершено',
  архив: 'Архив',
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

// Helpers — decimal fields stay strings end-to-end; empty → null.
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
  notes: optionalString,
  // Audience
  theme: optionalString,
  audience_age: optionalString,
  subscribers: optionalInt,
  min_reach: optionalInt,
  engagement_rate: optionalDecimal,
  // Fact metrics
  fact_views: optionalInt,
  fact_cpm: optionalDecimal,
  fact_clicks: optionalInt,
  fact_ctr: optionalDecimal,
  fact_cpc: optionalDecimal,
  fact_carts: optionalInt,
  cr_to_cart: optionalDecimal,
  fact_orders: optionalInt,
  cr_to_order: optionalDecimal,
  fact_revenue: optionalDecimal,
  // Content & links
  contract_url: optionalString,
  post_url: optionalString,
  tz_url: optionalString,
  screen_url: optionalString,
  post_content: optionalString,
  analysis: optionalString,
  recommended_models: optionalString,
  // Compliance (nullable booleans — tri-state: null=не проверено, false=нет, true=да)
  has_marking: z.boolean().nullable().optional().default(null),
  has_contract: z.boolean().nullable().optional().default(null),
  has_deeplink: z.boolean().nullable().optional().default(null),
  has_closing_docs: z.boolean().nullable().optional().default(null),
  has_full_recording: z.boolean().nullable().optional().default(null),
  all_data_filled: z.boolean().nullable().optional().default(null),
  has_quality_content: z.boolean().nullable().optional().default(null),
  complies_with_rules: z.boolean().nullable().optional().default(null),
});

type FormInput = z.input<typeof formSchema>;
type FormOutput = z.output<typeof formSchema>;

interface IntegrationEditDrawerProps {
  open: boolean;
  onClose: () => void;
  id?: number;
  initialDate?: string;
}

function defaultsFromDetail(detail?: IntegrationDetailOut, initialDate?: string): FormInput {
  return {
    blogger_id: detail?.blogger_id != null ? String(detail.blogger_id) : '',
    marketer_id: detail?.marketer_id != null ? String(detail.marketer_id) : '',
    publish_date: detail?.publish_date ?? initialDate ?? '',
    channel: detail?.channel ?? 'instagram',
    ad_format: detail?.ad_format ?? 'story',
    marketplace: detail?.marketplace ?? 'wb',
    stage: detail?.stage ?? 'переговоры',
    outcome: detail?.outcome ?? '',
    is_barter: detail?.is_barter ?? false,
    cost_placement: detail?.cost_placement ?? '',
    cost_delivery: detail?.cost_delivery ?? '',
    cost_goods: detail?.cost_goods ?? '',
    erid: detail?.erid ?? '',
    notes: detail?.notes ?? '',
    // Audience
    theme: detail?.theme ?? '',
    audience_age: detail?.audience_age ?? '',
    subscribers: detail?.subscribers != null ? String(detail.subscribers) : '',
    min_reach: detail?.min_reach != null ? String(detail.min_reach) : '',
    engagement_rate: detail?.engagement_rate ?? '',
    // Fact metrics
    fact_views: detail?.fact_views != null ? String(detail.fact_views) : '',
    fact_cpm: detail?.fact_cpm ?? '',
    fact_clicks: detail?.fact_clicks != null ? String(detail.fact_clicks) : '',
    fact_ctr: detail?.fact_ctr ?? '',
    fact_cpc: detail?.fact_cpc ?? '',
    fact_carts: detail?.fact_carts != null ? String(detail.fact_carts) : '',
    cr_to_cart: detail?.cr_to_cart ?? '',
    fact_orders: detail?.fact_orders != null ? String(detail.fact_orders) : '',
    cr_to_order: detail?.cr_to_order ?? '',
    fact_revenue: detail?.fact_revenue ?? '',
    // Content & links
    contract_url: detail?.contract_url ?? '',
    post_url: detail?.post_url ?? '',
    tz_url: detail?.tz_url ?? '',
    screen_url: detail?.screen_url ?? '',
    post_content: detail?.post_content ?? '',
    analysis: detail?.analysis ?? '',
    recommended_models: detail?.recommended_models ?? '',
    // Compliance
    has_marking: detail?.has_marking ?? null,
    has_contract: detail?.has_contract ?? null,
    has_deeplink: detail?.has_deeplink ?? null,
    has_closing_docs: detail?.has_closing_docs ?? null,
    has_full_recording: detail?.has_full_recording ?? null,
    all_data_filled: detail?.all_data_filled ?? null,
    has_quality_content: detail?.has_quality_content ?? null,
    complies_with_rules: detail?.complies_with_rules ?? null,
  };
}

export function IntegrationEditDrawer({
  open,
  onClose,
  id,
  initialDate,
}: IntegrationEditDrawerProps) {
  const isEdit = id !== undefined && id > 0;
  const detailQuery = useIntegration(isEdit ? id : undefined);
  const detail = isEdit ? detailQuery.data : undefined;

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultsFromDetail(detail, isEdit ? undefined : initialDate),
  });

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger
  useEffect(() => {
    if (open) {
      form.reset(defaultsFromDetail(detail, isEdit ? undefined : initialDate));
    }
  }, [open, detail?.id, detail?.updated_at, initialDate, isEdit]);

  const upsert = useUpsertIntegration();

  const title = isEdit
    ? `Интеграция #${id}${detail?.blogger_handle ? ` — ${detail.blogger_handle}` : ''}`
    : 'Новая интеграция';

  const onSubmit: SubmitHandler<FormOutput> = async (values) => {
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
      notes: values.notes,
      theme: values.theme,
      audience_age: values.audience_age,
      subscribers: values.subscribers,
      min_reach: values.min_reach,
      engagement_rate: values.engagement_rate,
      fact_views: values.fact_views,
      fact_cpm: values.fact_cpm,
      fact_clicks: values.fact_clicks,
      fact_ctr: values.fact_ctr,
      fact_cpc: values.fact_cpc,
      fact_carts: values.fact_carts,
      cr_to_cart: values.cr_to_cart,
      fact_orders: values.fact_orders,
      cr_to_order: values.cr_to_order,
      fact_revenue: values.fact_revenue,
      contract_url: values.contract_url,
      post_url: values.post_url,
      tz_url: values.tz_url,
      screen_url: values.screen_url,
      post_content: values.post_content,
      analysis: values.analysis,
      recommended_models: values.recommended_models,
      has_marking: values.has_marking,
      has_contract: values.has_contract,
      has_deeplink: values.has_deeplink,
      has_closing_docs: values.has_closing_docs,
      has_full_recording: values.has_full_recording,
      all_data_filled: values.all_data_filled,
      has_quality_content: values.has_quality_content,
      complies_with_rules: values.complies_with_rules,
    };
    await upsert.mutateAsync({ id: isEdit ? id : undefined, body });
    onClose();
  };

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
        <AudienceSection form={form} />
        <FactSection form={form} />
        <ContentSection form={form} />
        <ComplianceSection form={form} />
        <SubstitutesSection detail={detail} isEdit={isEdit} />
        {upsert.error && (
          <p className="text-sm text-danger">
            Не удалось сохранить:{' '}
            {upsert.error instanceof Error ? upsert.error.message : 'неизвестная ошибка'}
          </p>
        )}
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
    <Section title="Стоимость">
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

function AudienceSection({ form }: SectionProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const themeId = useId();
  const ageId = useId();
  const subscribersId = useId();
  const minReachId = useId();
  const erId = useId();

  return (
    <Section title="Аудитория">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Тематика" htmlFor={themeId} error={errors.theme?.message}>
          <Input id={themeId} placeholder="мода, лайфстайл, техника..." {...register('theme')} />
        </Field>

        <Field label="Возраст аудитории" htmlFor={ageId} error={errors.audience_age?.message}>
          <Input id={ageId} placeholder="25-34, 18-24..." {...register('audience_age')} />
        </Field>

        <Field label="Подписчики" htmlFor={subscribersId} error={errors.subscribers?.message}>
          <Input
            id={subscribersId}
            inputMode="numeric"
            placeholder="100000"
            {...register('subscribers')}
          />
        </Field>

        <Field label="Мин. охват" htmlFor={minReachId} error={errors.min_reach?.message}>
          <Input
            id={minReachId}
            inputMode="numeric"
            placeholder="15000"
            {...register('min_reach')}
          />
        </Field>

        <Field label="ER, %" htmlFor={erId} error={errors.engagement_rate?.message}>
          <Input
            id={erId}
            inputMode="decimal"
            placeholder="2.5"
            {...register('engagement_rate')}
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
  const cpmId = useId();
  const clicksId = useId();
  const ctrId = useId();
  const cpcId = useId();
  const cartsId = useId();
  const crToCartId = useId();
  const ordersId = useId();
  const crToOrderId = useId();
  const revenueId = useId();

  return (
    <Section title="Факт">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Просмотры" htmlFor={viewsId} error={errors.fact_views?.message}>
          <Input id={viewsId} inputMode="numeric" placeholder="0" {...register('fact_views')} />
        </Field>

        <Field label="CPM, ₽" htmlFor={cpmId} error={errors.fact_cpm?.message}>
          <Input id={cpmId} inputMode="decimal" placeholder="0" {...register('fact_cpm')} />
        </Field>

        <Field label="Клики" htmlFor={clicksId} error={errors.fact_clicks?.message}>
          <Input id={clicksId} inputMode="numeric" placeholder="0" {...register('fact_clicks')} />
        </Field>

        <Field label="CTR, %" htmlFor={ctrId} error={errors.fact_ctr?.message}>
          <Input id={ctrId} inputMode="decimal" placeholder="0" {...register('fact_ctr')} />
        </Field>

        <Field label="CPC, ₽" htmlFor={cpcId} error={errors.fact_cpc?.message}>
          <Input id={cpcId} inputMode="decimal" placeholder="0" {...register('fact_cpc')} />
        </Field>

        <Field label="Корзины" htmlFor={cartsId} error={errors.fact_carts?.message}>
          <Input id={cartsId} inputMode="numeric" placeholder="0" {...register('fact_carts')} />
        </Field>

        <Field label="CR → корзина, %" htmlFor={crToCartId} error={errors.cr_to_cart?.message}>
          <Input
            id={crToCartId}
            inputMode="decimal"
            placeholder="0"
            {...register('cr_to_cart')}
          />
        </Field>

        <Field label="Заказы, шт" htmlFor={ordersId} error={errors.fact_orders?.message}>
          <Input id={ordersId} inputMode="numeric" placeholder="0" {...register('fact_orders')} />
        </Field>

        <Field label="CR → заказ, %" htmlFor={crToOrderId} error={errors.cr_to_order?.message}>
          <Input
            id={crToOrderId}
            inputMode="decimal"
            placeholder="0"
            {...register('cr_to_order')}
          />
        </Field>

        <Field label="Выручка, ₽" htmlFor={revenueId} error={errors.fact_revenue?.message}>
          <Input
            id={revenueId}
            inputMode="decimal"
            placeholder="0"
            {...register('fact_revenue')}
          />
        </Field>
      </div>
    </Section>
  );
}

function ContentSection({ form }: SectionProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const contractId = useId();
  const postUrlId = useId();
  const tzId = useId();
  const screenId = useId();
  const postContentId = useId();
  const analysisId = useId();
  const modelsId = useId();
  const notesId = useId();
  const eridId = useId();

  return (
    <Section title="Контент и ссылки">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Ссылка на договор" htmlFor={contractId} error={errors.contract_url?.message}>
          <Input
            id={contractId}
            type="url"
            placeholder="https://..."
            {...register('contract_url')}
          />
        </Field>

        <Field label="Ссылка на пост" htmlFor={postUrlId} error={errors.post_url?.message}>
          <Input id={postUrlId} type="url" placeholder="https://..." {...register('post_url')} />
        </Field>

        <Field label="Ссылка на ТЗ" htmlFor={tzId} error={errors.tz_url?.message}>
          <Input id={tzId} type="url" placeholder="https://..." {...register('tz_url')} />
        </Field>

        <Field label="Скриншот" htmlFor={screenId} error={errors.screen_url?.message}>
          <Input id={screenId} type="url" placeholder="https://..." {...register('screen_url')} />
        </Field>

        <Field label="ERID" htmlFor={eridId} error={errors.erid?.message}>
          <Input id={eridId} placeholder="напр. 2VtzqwYjJjA" {...register('erid')} />
        </Field>

        <Field label="Рекомендуемые модели" htmlFor={modelsId} error={errors.recommended_models?.message}>
          <Input id={modelsId} placeholder="модель1, модель2..." {...register('recommended_models')} />
        </Field>

        <div className="sm:col-span-2">
          <Field label="Текст поста" htmlFor={postContentId} error={errors.post_content?.message}>
            <Textarea id={postContentId} rows={4} {...register('post_content')} />
          </Field>
        </div>

        <div className="sm:col-span-2">
          <Field label="Анализ" htmlFor={analysisId} error={errors.analysis?.message}>
            <Textarea id={analysisId} rows={3} placeholder="выводы по интеграции..." {...register('analysis')} />
          </Field>
        </div>

        <div className="sm:col-span-2">
          <Field label="Заметки" htmlFor={notesId} error={errors.notes?.message}>
            <Textarea
              id={notesId}
              rows={3}
              placeholder="ТЗ, договорённости, ссылки..."
              {...register('notes')}
            />
          </Field>
        </div>
      </div>
    </Section>
  );
}

function ComplianceSection({ form }: SectionProps) {
  return (
    <Section title="Compliance">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {(
          [
            ['has_marking', 'Маркировка'],
            ['has_contract', 'Договор'],
            ['has_deeplink', 'Диплинк'],
            ['has_closing_docs', 'Закрывающие'],
            ['has_full_recording', 'Полная запись'],
            ['all_data_filled', 'Данные заполнены'],
            ['has_quality_content', 'Качество контента'],
            ['complies_with_rules', 'Соответствие правилам'],
          ] as const
        ).map(([field]) => (
          <ComplianceCheckbox key={field} form={form} field={field} />
        ))}
      </div>
    </Section>
  );
}

const COMPLIANCE_LABELS: Record<string, string> = {
  has_marking: 'Маркировка',
  has_contract: 'Договор',
  has_deeplink: 'Диплинк',
  has_closing_docs: 'Закрывающие',
  has_full_recording: 'Полная запись',
  all_data_filled: 'Данные заполнены',
  has_quality_content: 'Качество контента',
  complies_with_rules: 'Соответствие правилам',
};

function ComplianceCheckbox({
  form,
  field,
}: {
  form: UseFormReturn<FormInput, unknown, FormOutput>;
  field: keyof typeof COMPLIANCE_LABELS;
}) {
  const checkId = useId();
  return (
    <div className="flex items-center gap-2">
      <input
        id={checkId}
        type="checkbox"
        className="size-4 rounded border-border"
        {...form.register(field as keyof FormInput)}
      />
      <label htmlFor={checkId} className="text-sm text-fg">
        {COMPLIANCE_LABELS[field]}
      </label>
    </div>
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
          description="Привязываются через ETL из Google Sheets."
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
