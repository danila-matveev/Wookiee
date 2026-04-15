import { useParams, useNavigate } from "react-router-dom";
import { useMemo } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { useApiQuery } from "@/hooks/use-api-query";
import { get } from "@/lib/api-client";
import { matrixApi, type ModelVariation, type PaginatedResponse, type Artikul, type Tovar } from "@/lib/matrix-api";
import { InfoTab } from "@/components/matrix/tabs/info-tab";
import { StockTab } from "@/components/matrix/tabs/stock-tab";
import { FinanceTab } from "@/components/matrix/tabs/finance-tab";
import { RatingTab } from "@/components/matrix/tabs/rating-tab";
import { TasksTab } from "@/components/matrix/tabs/tasks-tab";

const ENTITIES_WITH_MP = new Set([
  "models_osnova", "models", "articles", "products", "cards_wb", "cards_ozon",
]);

const ENTITY_LABELS: Record<string, string> = {
  models_osnova: "Модель основа",
  models: "Модель",
  articles: "Артикул",
  products: "Товар",
  colors: "Цвет",
  cards_wb: "Склейка WB",
  cards_ozon: "Склейка Ozon",
  factories: "Фабрика",
  importers: "Импортёр",
  certs: "Сертификат",
};

// Entity types that have children and how to fetch them
const CHILDREN_ENTITY_TYPES = new Set(["models_osnova", "models", "articles"]);

export function EntityDetailPage() {
  const { entity, id } = useParams<{ entity: string; id: string }>();
  const navigate = useNavigate();
  const entityId = Number(id);

  const fetchEntity = () => {
    switch (entity) {
      case "models_osnova": return matrixApi.getModel(entityId);
      case "articles": return matrixApi.getArticle(entityId);
      case "products": return matrixApi.getProduct(entityId);
      default: return get<Record<string, unknown>>(`/api/matrix/${entity}/${entityId}`);
    }
  };

  const { data, loading } = useApiQuery(fetchEntity, [entity, entityId]);

  // Fetch children based on entity type
  const hasChildren = entity ? CHILDREN_ENTITY_TYPES.has(entity) : false;

  const fetchChildren = () => {
    switch (entity) {
      case "models_osnova":
        return matrixApi.listChildren(entityId) as Promise<unknown>;
      case "models":
        return matrixApi.listArticles({ model_id: entityId }) as Promise<unknown>;
      case "articles":
        return matrixApi.listProducts({ artikul_id: entityId }) as Promise<unknown>;
      default:
        return Promise.resolve(null);
    }
  };

  const { data: childrenData } = useApiQuery(fetchChildren, [entity, entityId]);

  const childrenGroups = useMemo(() => {
    if (!childrenData || !entity) return [];

    switch (entity) {
      case "models_osnova": {
        const variations = childrenData as ModelVariation[];
        return [{
          type: "models",
          label: "Модели",
          items: variations.map((v) => ({ id: v.id, name: v.nazvanie || v.kod })),
        }];
      }
      case "models": {
        const resp = childrenData as PaginatedResponse<Artikul>;
        return [{
          type: "articles",
          label: "Артикулы",
          items: (resp.items ?? []).map((a) => ({ id: a.id, name: a.artikul })),
        }];
      }
      case "articles": {
        const resp = childrenData as PaginatedResponse<Tovar>;
        return [{
          type: "products",
          label: "Товары",
          items: (resp.items ?? []).map((t) => ({ id: t.id, name: t.barkod })),
        }];
      }
      default:
        return [];
    }
  }, [childrenData, entity]);

  const hasMp = entity ? ENTITIES_WITH_MP.has(entity) : false;
  const entityLabel = entity ? (ENTITY_LABELS[entity] ?? entity) : "";
  const entityName = data ? (data as Record<string, unknown>).kod ?? (data as Record<string, unknown>).nazvanie ?? `#${entityId}` : `#${entityId}`;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Назад
        </Button>
        <div className="flex-1">
          <h1 className="text-lg font-semibold">{String(entityName)}</h1>
          <p className="text-sm text-muted-foreground">{entityLabel}</p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="info" className="flex-1">
        <TabsList className="mx-4 mt-2">
          <TabsTrigger value="info">Информация</TabsTrigger>
          {hasMp && <TabsTrigger value="stock">Остатки</TabsTrigger>}
          {hasMp && <TabsTrigger value="finance">Финансы</TabsTrigger>}
          {hasMp && <TabsTrigger value="rating">Рейтинг</TabsTrigger>}
          <TabsTrigger value="tasks">Задачи</TabsTrigger>
        </TabsList>

        <TabsContent value="info" className="mt-0">
          {loading ? (
            <div className="p-4 text-muted-foreground">Загрузка...</div>
          ) : data ? (
            <InfoTab
              data={data as Record<string, unknown>}
              entityType={entity ?? ""}
              children={childrenGroups.length > 0 ? childrenGroups : undefined}
            />
          ) : (
            <div className="p-4 text-muted-foreground">Запись не найдена</div>
          )}
        </TabsContent>

        {hasMp && entity && (
          <>
            <TabsContent value="stock" className="mt-0">
              <StockTab entityType={entity} entityId={entityId} />
            </TabsContent>

            <TabsContent value="finance" className="mt-0">
              <FinanceTab entityType={entity} entityId={entityId} />
            </TabsContent>

            <TabsContent value="rating" className="mt-0">
              <RatingTab />
            </TabsContent>
          </>
        )}

        <TabsContent value="tasks" className="mt-0">
          <TasksTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
