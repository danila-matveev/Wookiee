import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useId } from 'react';
import { type SubmitHandler, useForm } from 'react-hook-form';
import { z } from 'zod';
import {
  BRIEF_STATUS_LABELS,
  type BriefCreateInput,
  type BriefDetailOut,
  type BriefStatus,
} from '@/api/briefs';
import {
  useAddBriefVersion,
  useBrief,
  useCreateBrief,
  useUpdateBriefStatus,
} from '@/hooks/use-briefs';
import { Button } from '@/ui/Button';
import { Drawer } from '@/ui/Drawer';
import { Input } from '@/ui/Input';
import { Tabs } from '@/ui/Tabs';
import { Textarea } from '@/ui/Textarea';

// Reused validators — int IDs are optional strings; empty → null.
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
  title: z.string().trim().min(1, 'Обязательное поле').max(300, 'Не больше 300 символов'),
  blogger_id: optionalIntId,
  integration_id: optionalIntId,
  content_md: z.string().min(1, 'Заполните содержимое брифа'),
});

type FormInput = z.input<typeof formSchema>;
type FormOutput = z.output<typeof formSchema>;

interface BriefEditorDrawerProps {
  open: boolean;
  onClose: () => void;
  /** When set AND > 0, drawer is in edit mode and loads detail. */
  id?: number;
}

function defaultsFromDetail(detail?: BriefDetailOut): FormInput {
  return {
    title: detail?.title ?? '',
    blogger_id: detail?.blogger_id != null ? String(detail.blogger_id) : '',
    integration_id: detail?.integration_id != null ? String(detail.integration_id) : '',
    content_md: detail?.content_md ?? '',
  };
}

const STATUS_FLOW: { from: BriefStatus; to: BriefStatus; label: string }[] = [
  { from: 'draft', to: 'on_review', label: 'Отправить на ревью' },
  { from: 'on_review', to: 'signed', label: 'Подписать' },
  { from: 'signed', to: 'completed', label: 'Завершить' },
];

export function BriefEditorDrawer({ open, onClose, id }: BriefEditorDrawerProps) {
  const isEdit = id !== undefined && id > 0;
  const detailQuery = useBrief(isEdit ? id : undefined);
  const detail = isEdit ? detailQuery.data : undefined;

  const form = useForm<FormInput, unknown, FormOutput>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultsFromDetail(detail),
  });

  // Reset form whenever the drawer opens or a different brief loads.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional reset trigger
  useEffect(() => {
    if (open) {
      form.reset(defaultsFromDetail(detail));
    }
  }, [open, detail?.id, detail?.updated_at, detail?.current_version]);

  const createMut = useCreateBrief();
  const addVersionMut = useAddBriefVersion();
  const statusMut = useUpdateBriefStatus();

  const titleId = useId();
  const bloggerIdField = useId();
  const integrationIdField = useId();
  const contentMdField = useId();

  const isSaving = createMut.isPending || addVersionMut.isPending;
  const saveError = createMut.error ?? addVersionMut.error ?? statusMut.error;

  const drawerTitle = isEdit
    ? `Бриф #${id}${detail?.title ? ` — ${detail.title}` : ''}`
    : 'Новый бриф';

  const onSubmit: SubmitHandler<FormOutput> = async (values) => {
    if (isEdit && id) {
      // EDIT mode: bump the version with new markdown content.
      // Title/meta updates would require a PATCH endpoint that the BFF doesn't yet
      // expose; the version POST is the supported atomic mutation today.
      await addVersionMut.mutateAsync({ id, content_md: values.content_md });
    } else {
      const body: BriefCreateInput = {
        title: values.title,
        content_md: values.content_md,
      };
      if (values.blogger_id != null) body.blogger_id = values.blogger_id;
      if (values.integration_id != null) body.integration_id = values.integration_id;
      await createMut.mutateAsync(body);
    }
    onClose();
  };

  const versions = detail?.versions ?? [];
  const currentStatus: BriefStatus = detail?.status ?? 'draft';
  const nextTransition = STATUS_FLOW.find((s) => s.from === currentStatus);

  const editorTab = (
    <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={titleId} className="text-xs font-medium text-muted-fg">
          Заголовок*
        </label>
        <Input
          id={titleId}
          placeholder="Например, ТЗ для Анны / WB / сторис"
          {...form.register('title')}
        />
        {form.formState.errors.title && (
          <p className="text-xs text-danger">{form.formState.errors.title.message}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label htmlFor={bloggerIdField} className="text-xs font-medium text-muted-fg">
            ID блогера
          </label>
          <Input
            id={bloggerIdField}
            inputMode="numeric"
            placeholder="например, 11"
            {...form.register('blogger_id')}
          />
          {form.formState.errors.blogger_id && (
            <p className="text-xs text-danger">{form.formState.errors.blogger_id.message}</p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor={integrationIdField} className="text-xs font-medium text-muted-fg">
            ID интеграции
          </label>
          <Input
            id={integrationIdField}
            inputMode="numeric"
            placeholder="опционально"
            {...form.register('integration_id')}
          />
          {form.formState.errors.integration_id && (
            <p className="text-xs text-danger">{form.formState.errors.integration_id.message}</p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={contentMdField} className="text-xs font-medium text-muted-fg">
          Содержимое (markdown)*
        </label>
        <Textarea
          id={contentMdField}
          rows={16}
          className="font-mono"
          placeholder={'# Заголовок\n\n- Пункт 1\n- Пункт 2'}
          {...form.register('content_md')}
        />
        {form.formState.errors.content_md && (
          <p className="text-xs text-danger">{form.formState.errors.content_md.message}</p>
        )}
      </div>

      {saveError && (
        <p className="text-sm text-danger">
          Не удалось сохранить:{' '}
          {saveError instanceof Error ? saveError.message : 'неизвестная ошибка'}
        </p>
      )}

      {/* Hidden submit so Enter inside title triggers handleSubmit. */}
      <button type="submit" hidden aria-hidden="true" tabIndex={-1} />
    </form>
  );

  const historyTab = (
    <div className="flex flex-col gap-3">
      {versions.length === 0 ? (
        <p className="rounded-md border border-dashed border-border px-3 py-6 text-center text-sm text-muted-fg">
          {isEdit ? 'Версий ещё нет' : 'Сохраните бриф, чтобы появилась первая версия'}
        </p>
      ) : (
        versions.map((v) => (
          <article
            key={v.id}
            className="rounded-md border border-border bg-card p-3"
            data-testid={`brief-version-${v.version}`}
          >
            <header className="mb-2 flex items-center justify-between">
              <span className="font-display text-sm font-semibold text-fg">v{v.version}</span>
              {v.created_at && (
                <span className="font-mono text-[11px] text-muted-fg">
                  {new Date(v.created_at).toLocaleString('ru-RU')}
                </span>
              )}
            </header>
            <pre className="whitespace-pre-wrap break-words font-mono text-xs text-fg">
              {v.content_md}
            </pre>
          </article>
        ))
      )}
    </div>
  );

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={drawerTitle}
      width="max-w-2xl"
      footer={
        <>
          {isEdit && nextTransition && (
            <Button
              variant="ghost"
              onClick={() => id && statusMut.mutate({ id, status: nextTransition.to })}
              loading={statusMut.isPending}
            >
              {nextTransition.label}
            </Button>
          )}
          <Button variant="secondary" onClick={onClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button variant="primary" loading={isSaving} onClick={form.handleSubmit(onSubmit)}>
            {isEdit ? 'Создать новую версию' : 'Сохранить как черновик'}
          </Button>
        </>
      }
    >
      <Tabs
        tabs={[
          { label: 'Бриф', content: editorTab },
          { label: 'История версий', content: historyTab, count: versions.length || undefined },
        ]}
      />
    </Drawer>
  );
}

export const BRIEF_STATUS_FLOW = STATUS_FLOW;
export { BRIEF_STATUS_LABELS };
export default BriefEditorDrawer;
