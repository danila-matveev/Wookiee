import { Link } from "react-router-dom";
import { useApiQuery } from "@/hooks/use-api-query";
import { matrixApi, type FieldDefinition } from "@/lib/matrix-api";
import { useMemo } from "react";

interface InfoTabProps {
  data: Record<string, unknown>;
  entityType: string;
  children?: Array<{ type: string; label: string; items: Array<{ id: number; name: string }> }>;
}

const FIELD_DEF_ENTITY_MAP: Record<string, string> = {
  models_osnova: "modeli_osnova",
  models: "modeli",
  articles: "artikuly",
  products: "tovary",
  colors: "cveta",
  factories: "fabriki",
  importers: "importery",
  cards_wb: "skleyki_wb",
  cards_ozon: "skleyki_ozon",
  certs: "sertifikaty",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">{title}</h3>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2">{children}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: unknown }) {
  const display = value == null || value === "" ? "—" : String(value);
  return (
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm">{display}</span>
    </div>
  );
}

function RelatedList({ title, entityType, items }: {
  title: string;
  entityType: string;
  items: Array<{ id: number; name: string }>;
}) {
  if (!items.length) return null;
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-medium text-muted-foreground">{title} ({items.length})</h4>
      <ul className="space-y-0.5">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              to={`/product/matrix/${entityType}/${item.id}`}
              className="text-sm text-primary hover:underline"
            >
              {item.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Fields to skip in display (internal/technical)
const SKIP_FIELDS = new Set(["id", "created_at", "updated_at", "status_id"]);

interface FieldGroup {
  section: string;
  fields: Array<{ key: string; label: string; value: unknown }>;
}

export function InfoTab({ data, entityType, children }: InfoTabProps) {
  const fieldDefEntityType = FIELD_DEF_ENTITY_MAP[entityType] ?? entityType;

  const { data: fieldDefs } = useApiQuery<FieldDefinition[]>(
    () => matrixApi.listFields(fieldDefEntityType),
    [fieldDefEntityType],
  );

  const groups = useMemo(() => {
    const dataEntries = Object.entries(data).filter(([k]) => !SKIP_FIELDS.has(k));

    if (!fieldDefs || fieldDefs.length === 0) {
      // Fallback: single section with raw keys
      return [{
        section: "Основные",
        fields: dataEntries.map(([key, value]) => ({ key, label: key, value })),
      }] as FieldGroup[];
    }

    // Build lookup from field_name to definition
    const defMap = new Map<string, FieldDefinition>();
    for (const fd of fieldDefs) {
      defMap.set(fd.field_name, fd);
    }

    // Collect visible fields with definitions, sorted by sort_order
    const definedFields: Array<{ key: string; label: string; value: unknown; section: string; sortOrder: number }> = [];
    const unmatchedFields: Array<{ key: string; label: string; value: unknown }> = [];

    for (const [key, value] of dataEntries) {
      const def = defMap.get(key);
      if (def) {
        if (!def.is_visible) continue;
        definedFields.push({
          key,
          label: def.display_name,
          value,
          section: def.section ?? "Основные",
          sortOrder: def.sort_order,
        });
      } else {
        unmatchedFields.push({ key, label: key, value });
      }
    }

    // Sort by sort_order within each section
    definedFields.sort((a, b) => a.sortOrder - b.sortOrder);

    // Group by section preserving order of first appearance
    const sectionMap = new Map<string, FieldGroup>();
    for (const f of definedFields) {
      let group = sectionMap.get(f.section);
      if (!group) {
        group = { section: f.section, fields: [] };
        sectionMap.set(f.section, group);
      }
      group.fields.push({ key: f.key, label: f.label, value: f.value });
    }

    const result = Array.from(sectionMap.values());

    // Append unmatched fields to an "Прочие" section if any
    if (unmatchedFields.length > 0) {
      result.push({ section: "Прочие", fields: unmatchedFields });
    }

    return result;
  }, [data, fieldDefs]);

  return (
    <div className="space-y-6 p-4">
      {groups.map((group) => (
        <Section key={group.section} title={group.section}>
          {group.fields.map((f) => (
            <Field key={f.key} label={f.label} value={f.value} />
          ))}
        </Section>
      ))}

      {children && children.length > 0 && (
        <div className="space-y-4 border-t pt-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Связанные</h3>
          {children.map((group) => (
            <RelatedList
              key={group.type}
              title={group.label}
              entityType={group.type}
              items={group.items}
            />
          ))}
        </div>
      )}
    </div>
  );
}
