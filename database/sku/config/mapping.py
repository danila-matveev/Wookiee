"""
Маппинг колонок Excel → База данных

Соответствие между названиями столбцов в Google Sheets/Excel
и полями в базе данных PostgreSQL.
"""
from typing import Optional

# ============================================
# ЛИСТ "ВСЕ МОДЕЛИ" → ТАБЛИЦА modeli
# ============================================

MAPPING_MODELI = {
    # Excel колонка → Поле БД

    # Основные поля
    'Название модели': 'nazvanie',
    'Name': 'nazvanie_en',
    'Артикул модели': 'artikul_modeli',
    'Модель основа': '_model_osnova',  # требует lookup
    'Категория': '_kategoriya',  # требует lookup
    'Коллекция': '_kollekciya',  # требует lookup
    'Статус': '_status',  # требует lookup
    'Импортер': '_importer',  # требует lookup
    'Фабрика': '_fabrika',  # требует lookup
    'Набор': 'nabor',
    'Размеры модели': 'razmery_modeli',
    'Российский размер': 'rossiyskiy_razmer',

    # Характеристики модели
    'Для какой груди': 'dlya_kakoy_grudi',
    'Степень поддержки груди/в характеристике карточки': 'stepen_podderzhki',
    'Форма чашки': 'forma_chashki',
    'Регулировка': 'regulirovka',
    'Застежка': 'zastezhka',
    'Посадка трусов': 'posadka_trusov',
    'Вид трусов': 'vid_trusov',
    'Назначение': 'naznachenie',
    'Стиль': 'stil',
    'По настроению': 'po_nastroeniyu',
    'Материал': 'material',
    'Состав сырья': 'sostav_syrya',
    'Composition': 'composition',

    # Упаковка и логистика
    'SKU CHINA': 'sku_china',
    'Упаковка': 'upakovka',
    'Вес (кг)': 'ves_kg',
    'Длина': 'dlina_cm',
    'Ширина': 'shirina_cm',
    'Высота': 'vysota_cm',
    'Кратность короба': 'kratnost_koroba',
    'Срок производства': 'srok_proizvodstva',
    'Комплектация': 'komplektaciya',
    'ТНВЭД': 'tnved',
    'Группа': 'gruppa_sertifikata',

    # Контент
    'Название для Этикетки': 'nazvanie_etiketka',
    'Название для сайта': 'nazvanie_sayt',
    'Описание для сайта': 'opisanie_sayt',
    'Details': 'details',
    'Description': 'description',
    'Теги': 'tegi',
    'Ссылка на ноушн': 'notion_link',
}

# ============================================
# ЛИСТ "ВСЕ ТОВАРЫ" → ТАБЛИЦА tovary
# ============================================

MAPPING_TOVARY = {
    # Excel колонка → Поле БД

    # Баркоды
    'БАРКОД ': 'barkod',
    'БАРКОД GS1': 'barkod_gs1',
    'БАРКОД GS2': 'barkod_gs2',
    'БАРКОД ПЕРЕХОД': 'barkod_perehod',

    # Связи (требуют lookup)
    'Артикул': '_artikul',
    'Размер': '_razmer',

    # Статусы
    'Статус товара': '_status',
    'Статус товара OZON': '_status_ozon',

    # Идентификаторы маркетплейсов
    'Ozon Product ID': 'ozon_product_id',
    'FBO OZON SKU ID': 'ozon_fbo_sku_id',
    'Seller SKU Lamoda': 'lamoda_seller_sku',
    'SKU CHINA SIZE': 'sku_china_size',

    # Для создания артикула (если не существует)
    'Модель': '_model_name',
    'Color code': '_color_code',
    'Склейка на WB': '_skleyka_wb',
}

# ============================================
# ЛИСТ "АНАЛИТИКА ЦВЕТОВ" → ТАБЛИЦА cveta
# ============================================

MAPPING_CVETA = {
    'Color code': 'color_code',
    'Цвет': 'cvet',
    'Сolor': 'color',
    'Gusset': 'lastovica',
    'Статус': '_status',  # требует lookup
}

# ============================================
# ЛИСТ "СКЛЕЙКИ WB" → ТАБЛИЦА skleyki_wb
# ============================================

MAPPING_SKLEYKI_WB = {
    'Название склейки': 'nazvanie',
    'Импортер': '_importer',  # требует lookup
}

# ============================================
# СПРАВОЧНИКИ ЗНАЧЕНИЙ
# ============================================

# Единые статусы (для моделей, артикулов, цветов, товаров)
STATUSY = [
    'Продается',
    'Выводим',
    'Архив',
    'Подготовка',
    'План',
    'Новый',
    'Запуск',
]

# Маппинг старых модельных статусов → единые
MODEL_STATUS_MAP = {
    'В продаже': 'Продается',
    'Планирование': 'План',
    'Закуп': 'Подготовка',
    'В разработке': 'Подготовка',
    'Делаем образец': 'Новый',
}

# Категории
KATEGORII = [
    'Комплект белья',
    'Трусы',
    'Боди женское',
]

# Коллекции
KOLLEKCII = [
    'Трикотажное белье без вкладышей',
    'Трикотажное белье',
    'Трикотажное белье без вставок',
    'Наборы трусов',
    'Трикотажное белье с вкладышами',
    'Хлопковая коллекция',
    'Бесшовное белье Jelly',
]

# Размеры (с порядком сортировки)
RAZMERY = [
    ('XS', 1),
    ('S', 2),
    ('M', 3),
    ('L', 4),
    ('XL', 5),
    ('XXL', 6),
]

# Импортеры
IMPORTERY = [
    'ИП Медведева П.В.',
    'ООО Вуки',
]

# Базовые модели (Модель основа)
MODELI_OSNOVA = [
    'Vuki', 'Set Vuki', 'Moon', 'Set Moon', 'Ruby', 'Set Ruby',
    'Joy', 'Alice', 'Valery', 'Audrey', 'Wendy', 'Miafull',
    'Bella', 'Lana', 'Eva', 'Set Wendy', 'Charlotte', 'Jess',
    'Duo', 'Space', 'Mia', 'Angelina',
]


# ============================================
# ФУНКЦИИ ПРЕОБРАЗОВАНИЯ
# ============================================

def clean_barcode(value) -> Optional[str]:
    """Очистка и форматирование баркода"""
    if value is None or str(value).strip() == '' or str(value) == 'nan':
        return None

    # Преобразуем в строку и убираем научную нотацию
    if isinstance(value, float):
        value = f"{int(value)}"
    else:
        value = str(value).strip()

    # Убираем .0 в конце если есть
    if value.endswith('.0'):
        value = value[:-2]

    return value if value else None


def clean_string(value) -> Optional[str]:
    """Очистка строкового значения"""
    if value is None or str(value).strip() == '' or str(value) == 'nan':
        return None
    return str(value).strip()


def clean_numeric(value) -> Optional[float]:
    """Очистка числового значения"""
    if value is None or str(value).strip() == '' or str(value) == 'nan':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_integer(value) -> Optional[int]:
    """Очистка целочисленного значения"""
    if value is None or str(value).strip() == '' or str(value) == 'nan':
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def clean_boolean(value) -> bool:
    """Преобразование в булево значение"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    str_val = str(value).lower().strip()
    return str_val in ('да', 'yes', 'true', '1', 'д')
