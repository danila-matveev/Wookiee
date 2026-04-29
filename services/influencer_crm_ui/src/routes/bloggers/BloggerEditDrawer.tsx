import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useId } from 'react';
import { type SubmitHandler, type UseFormReturn, useForm } from 'react-hook-form';
import { z } from 'zod';
import type { BloggerDetailOut, BloggerInput, BloggerStatus } from '@/api/bloggers';
import { useBlogger, useUpsertBlogger } from '@/hooks/use-bloggers';
import { Button } from '@/ui/Button';
import { Drawer } from '@/ui/Drawer';
import { EmptyState } from '@/ui/EmptyState';
import { Input } from '@/ui/Input';
import { Select } from '@/ui/Select';
import { Tabs } from '@/ui/Tabs';
import { Textarea } from '@/ui/Textarea';

const STATUS_OPTIONS: { value: BloggerStatus; label: string }[] = [
  { value: 'new', label: 'Новый' },
  { value: 'in_progress', label: 'В работе' },
  { value: 'active', label: 'Активный' },
  { value: 'paused', label: 'На паузе' },
];

const optionalString = z
  .string()
  .trim()
  .optional()
  .transform((v) => (v && v.length > 0 ? v : null));

const optionalDecimal = z
  .string()
  .trim()
  .optional()
  .transform((v) => (v && v.length > 0 ? v : null));

const optionalEmail = z
  .string()
  .trim()
  .optional()
  .superRefine((v, ctx) => {
    if (v && v.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
      ctx.addIssue({ code: 'custom', message: 'Некорректный email' });
    }
  })
  .transform((v) => (v && v.length > 0 ? v : null));

const optionalIntId = z
  .string()
  .trim()
  .optional()
  .superRefine((v, ctx) => {
    if (v && v.length > 0 && !/^\d+$/.test(v)) {
      ctx.addIssue({ code: 'custom', message: 'Должно быть целое число' });
    }
  })
  .transform((v) => (v && v.length > 0 ? Number(v) : null));

const formSchema = z.object({
  display_handle: z.string().trim().min(1, 'Обязательное поле').max(200),
  real_name: optionalString,
  status: z.enum(['active', 'in_progress', 'new', 'paused']),
  default_marketer_id: optionalIntId,
  price_story_default: optionalDecimal,
  price_reels_default: optionalDecimal,
  contact_tg: optionalString,
  contact_email: optionalEmail,
  contact_phone: optionalString,
  geo_country: optionalString,
  notes: optionalString,
});

type FormInput = z.input<typeof formSchema>;
type FormOutput = z.output<typeof formSchema>;

interface BloggerEditDrawerProps {
  open: boolean;
  onClose: () => void;
  /** When provided, drawer opens in edit mode and prefills from the cached/loaded detail. */
  bloggerId?: number;
}

function defaultsFromDetail(detail?: BloggerDetailOut): FormInput {
  return {
    display_handle: detail?.display_handle ?? '',
    real_name: detail?.real_name ?? '',
    status: detail?.status ?? 'new',
    default_marketer_id:
      detail?.default_marketer_id != null ? String(detail.default_marketer_id) : '',
    price_story_default: detail?.price_story_default ?? '',
    price_reels_default: detail?.price_reels_default ?? '',
    contact_tg: detail?.contact_tg ?? '',
    contact_email: detail?.contact_email ?? '',
    contact_phone: detail?.contact_phone ?? '',
    geo_country: detail?.geo_country?.join(', ') ?? '',
    notes: detail?.notes ?? '',
  };
}

export function BloggerEditDrawer({ open, onClose, bloggerId }: BloggerEditDrawerProps) {
  const isEdit = bloggerId !== undefined && bloggerId > 0;
  const detailQuery = useBlogger(isEdit ? bloggerId : 0);
  const detail = isEdit ? detailQuery.data : undefined;

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultsFromDetail(detail),
  });

  // Keep form in sync with the loaded detail / open transitions.
  // We only want to reset when the drawer opens or when a *different* blogger
  // is loaded (id/updated_at) — not on every form/detail object identity change.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger
  useEffect(() => {
    if (open) {
      form.reset(defaultsFromDetail(detail));
    }
  }, [open, detail?.id, detail?.updated_at]);

  const upsert = useUpsertBlogger();

  const title = isEdit ? `Редактирование: ${detail?.display_handle ?? '...'}` : 'Новый блогер';

  const onSubmit: SubmitHandler<FormOutput> = async (values) => {
    const body: BloggerInput = {
      display_handle: values.display_handle,
      real_name: values.real_name,
      status: values.status,
      default_marketer_id: values.default_marketer_id,
      price_story_default: values.price_story_default,
      price_reels_default: values.price_reels_default,
      contact_tg: values.contact_tg,
      contact_email: values.contact_email,
      contact_phone: values.contact_phone,
      notes: values.notes,
    };
    await upsert.mutateAsync({ id: isEdit ? bloggerId : undefined, body });
    onClose();
  };

  const tabs = [
    {
      label: 'Инфо',
      content: <InfoTab form={form} />,
    },
    {
      label: 'Каналы',
      content: <ChannelsTab detail={detail} isEdit={isEdit} />,
    },
    {
      label: 'Интеграции',
      content: <IntegrationsTab isEdit={isEdit} />,
    },
    {
      label: 'Compliance',
      content: <ComplianceTab />,
    },
  ];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
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
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
        <Tabs tabs={tabs} />
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

interface InfoTabProps {
  form: UseFormReturn<FormInput, unknown, FormOutput>;
}

function InfoTab({ form }: InfoTabProps) {
  const {
    register,
    formState: { errors },
  } = form;
  const handleId = useId();
  const realNameId = useId();
  const statusId = useId();
  const marketerId = useId();
  const priceStoryId = useId();
  const priceReelsId = useId();
  const tgId = useId();
  const emailId = useId();
  const phoneId = useId();
  const geoId = useId();
  const notesId = useId();

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <Field label="Handle*" htmlFor={handleId} error={errors.display_handle?.message}>
        <Input id={handleId} placeholder="например, anna.blog" {...register('display_handle')} />
      </Field>

      <Field label="Имя" htmlFor={realNameId} error={errors.real_name?.message}>
        <Input id={realNameId} placeholder="Anna" {...register('real_name')} />
      </Field>

      <Field label="Статус*" htmlFor={statusId} error={errors.status?.message}>
        <Select id={statusId} {...register('status')}>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>

      <Field
        label="ID маркетолога"
        htmlFor={marketerId}
        error={errors.default_marketer_id?.message}
      >
        <Input
          id={marketerId}
          inputMode="numeric"
          placeholder="например, 7"
          {...register('default_marketer_id')}
        />
      </Field>

      <Field
        label="Цена сторис, ₽"
        htmlFor={priceStoryId}
        error={errors.price_story_default?.message}
      >
        <Input
          id={priceStoryId}
          inputMode="decimal"
          placeholder="0"
          {...register('price_story_default')}
        />
      </Field>

      <Field
        label="Цена reels, ₽"
        htmlFor={priceReelsId}
        error={errors.price_reels_default?.message}
      >
        <Input
          id={priceReelsId}
          inputMode="decimal"
          placeholder="0"
          {...register('price_reels_default')}
        />
      </Field>

      <Field label="Telegram" htmlFor={tgId} error={errors.contact_tg?.message}>
        <Input id={tgId} placeholder="@username" {...register('contact_tg')} />
      </Field>

      <Field label="Email" htmlFor={emailId} error={errors.contact_email?.message}>
        <Input
          id={emailId}
          type="email"
          placeholder="anna@example.com"
          {...register('contact_email')}
        />
      </Field>

      <Field label="Телефон" htmlFor={phoneId} error={errors.contact_phone?.message}>
        <Input id={phoneId} placeholder="+7..." {...register('contact_phone')} />
      </Field>

      <Field label="Гео" htmlFor={geoId} error={errors.geo_country?.message}>
        <Input id={geoId} placeholder="RU, KZ" {...register('geo_country')} />
      </Field>

      <div className="sm:col-span-2">
        <Field label="Заметки" htmlFor={notesId} error={errors.notes?.message}>
          <Textarea id={notesId} rows={4} {...register('notes')} />
        </Field>
      </div>
    </div>
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

function ChannelsTab({ detail, isEdit }: { detail?: BloggerDetailOut; isEdit: boolean }) {
  if (!isEdit) {
    return (
      <EmptyState
        title="Сначала сохрани блогера"
        description="Каналы можно добавить после создания записи."
      />
    );
  }

  if (!detail) {
    return <p className="text-sm text-muted-fg">Загрузка...</p>;
  }

  if (detail.channels.length === 0) {
    return (
      <EmptyState
        title="Каналов пока нет"
        description="Добавление каналов будет доступно в следующих итерациях (T11+)."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {detail.channels.map((c) => (
        <li
          key={c.id}
          className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm"
        >
          <span>
            <span className="font-medium">{c.channel}</span>{' '}
            <span className="text-muted-fg">@{c.handle}</span>
          </span>
          {c.url && (
            <a
              href={c.url}
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
  );
}

function IntegrationsTab({ isEdit }: { isEdit: boolean }) {
  return (
    <EmptyState
      title="В разработке"
      description={
        isEdit
          ? 'Список интеграций по блогеру будет добавлен в T13 (драйвер интеграций).'
          : 'Реализация в T11+. Сначала сохрани блогера.'
      }
    />
  );
}

function ComplianceTab() {
  return (
    <div className="flex flex-col gap-3 text-sm text-muted-fg">
      <p>
        Согласие на хранение данных (152-ФЗ), маркировка ОРД при платных интеграциях. Поле для
        пометки «Маркировка обязательна» — добавим, когда понадобится.
      </p>
    </div>
  );
}

export default BloggerEditDrawer;
