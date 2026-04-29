"""
Скрипт миграции данных из Excel в PostgreSQL

ВЕРСИЯ 2.0 - Модель основа как верхний уровень
Загружает данные из файла Спецификации.xlsx в базу данных.

Использование:
    python scripts/migrate_data.py

Или с указанием пути к файлу:
    python scripts/migrate_data.py --file /path/to/Спецификации.xlsx
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Any

import pandas as pd
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Загружаем переменные окружения из .env (для Supabase)
load_dotenv(project_root / ".env")

from config.database import get_session, engine
from config.mapping import (
    MAPPING_MODELI, MAPPING_TOVARY, MAPPING_CVETA, MODEL_STATUS_MAP,
    clean_barcode, clean_string, clean_numeric, clean_integer, clean_boolean
)
from database.models import (
    Base, Kategoriya, Kollekciya, Status, Razmer, Importer, Fabrika,
    Cvet, ModelOsnova, Model, Artikul, Tovar, SleykaWB, SleykaOzon
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('migration.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class DataMigrator:
    """Класс для миграции данных из Excel в PostgreSQL"""

    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.session: Optional[Session] = None

        # Кэш для lookup
        self._kategorii: Dict[str, int] = {}
        self._kollekcii: Dict[str, int] = {}
        self._statusy: Dict[str, int] = {}
        self._razmery: Dict[str, int] = {}
        self._importery: Dict[str, int] = {}
        self._fabriki: Dict[str, int] = {}
        self._modeli_osnova: Dict[str, int] = {}
        self._cveta: Dict[str, int] = {}
        self._modeli: Dict[str, int] = {}
        self._artikuly: Dict[str, int] = {}
        self._skleyki_wb: Dict[str, int] = {}

    def run(self):
        """Запуск полной миграции"""
        logger.info(f"Начинаем миграцию из файла: {self.excel_path}")

        # Создаем таблицы
        logger.info("Создаем структуру БД...")
        Base.metadata.create_all(bind=engine)

        with get_session() as session:
            self.session = session

            try:
                # 1. Справочники (без привязки к modeli_osnova)
                self._migrate_kategorii()
                self._migrate_kollekcii()
                self._migrate_statusy()
                self._migrate_razmery()
                self._migrate_importery()
                self._migrate_fabriki()

                # 2. Цвета
                self._migrate_cveta()

                # 3. Модели основа (ВЕРХНИЙ УРОВЕНЬ с характеристиками)
                self._migrate_modeli_osnova()

                # 4. Модели (вариации на юрлицах)
                self._migrate_modeli()

                # 5. Склейки
                self._migrate_skleyki_wb()

                # 6. Артикулы (из листа "Все товары")
                self._migrate_artikuly()

                # 7. Товары
                self._migrate_tovary()

                session.commit()
                logger.info("Миграция успешно завершена!")

                # Статистика
                self._print_stats()

            except Exception as e:
                session.rollback()
                logger.error(f"Ошибка миграции: {e}")
                raise

    def _print_stats(self):
        """Вывод статистики миграции"""
        logger.info("=" * 50)
        logger.info("СТАТИСТИКА МИГРАЦИИ:")
        logger.info(f"  Категории: {len(self._kategorii)}")
        logger.info(f"  Коллекции: {len(self._kollekcii)}")
        logger.info(f"  Импортеры: {len(self._importery)}")
        logger.info(f"  Фабрики: {len(self._fabriki)}")
        logger.info(f"  Цвета: {len(self._cveta)}")
        logger.info(f"  Модели основа: {len(self._modeli_osnova)}")
        logger.info(f"  Модели: {len(self._modeli)}")
        logger.info(f"  Склейки WB: {len(self._skleyki_wb)}")
        logger.info(f"  Артикулы: {len(self._artikuly)}")
        logger.info("=" * 50)

    def _load_sheet(self, sheet_name: str) -> pd.DataFrame:
        """Загрузка листа Excel"""
        logger.info(f"Загружаем лист: {sheet_name}")
        df = pd.read_excel(self.excel_path, sheet_name=sheet_name, header=0)
        logger.info(f"  Загружено {len(df)} строк")
        return df

    # ============================================
    # СПРАВОЧНИКИ
    # ============================================

    def _migrate_kategorii(self):
        """Миграция категорий"""
        logger.info("Миграция категорий...")
        df = self._load_sheet('Все модели')

        unique_values = df['Категория'].dropna().unique()
        for value in unique_values:
            value = clean_string(value)
            if value and value not in self._kategorii:
                obj = Kategoriya(nazvanie=value)
                self.session.add(obj)
                self.session.flush()
                self._kategorii[value] = obj.id

        logger.info(f"  Создано {len(self._kategorii)} категорий")

    def _migrate_kollekcii(self):
        """Миграция коллекций"""
        logger.info("Миграция коллекций...")
        df = self._load_sheet('Все модели')

        unique_values = df['Коллекция'].dropna().unique()
        for value in unique_values:
            value = clean_string(value)
            if value and value not in self._kollekcii:
                obj = Kollekciya(nazvanie=value)
                self.session.add(obj)
                self.session.flush()
                self._kollekcii[value] = obj.id

        logger.info(f"  Создано {len(self._kollekcii)} коллекций")

    def _migrate_statusy(self):
        """Миграция единых статусов"""
        logger.info("Миграция статусов...")

        all_names = set()

        # Статусы из моделей (с маппингом старых имён)
        df_models = self._load_sheet('Все модели')
        for value in df_models['Статус'].dropna().unique():
            value = clean_string(value)
            if value:
                all_names.add(MODEL_STATUS_MAP.get(value, value))

        # Статусы из товаров
        df_products = self._load_sheet('Все товары')
        for col in ['Статус товара', 'Статус товара OZON']:
            if col in df_products.columns:
                for value in df_products[col].dropna().unique():
                    value = clean_string(value)
                    if value:
                        all_names.add(value)

        # Статусы из цветов
        df_colors = self._load_sheet('Аналитики цветов')
        for value in df_colors['Статус'].dropna().unique():
            value = clean_string(value)
            if value:
                all_names.add(value)

        # Создаём единые записи
        for name in sorted(all_names):
            if name not in self._statusy:
                obj = Status(nazvanie=name)
                self.session.add(obj)
                self.session.flush()
                self._statusy[name] = obj.id

        logger.info(f"  Создано {len(self._statusy)} единых статусов")

    def _migrate_razmery(self):
        """Миграция размеров"""
        logger.info("Миграция размеров...")

        razmery_order = {'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5, 'XXL': 6}
        df = self._load_sheet('Все товары')

        for value in df['Размер'].dropna().unique():
            value = clean_string(value)
            if value and value not in self._razmery:
                poryadok = razmery_order.get(value, 99)
                obj = Razmer(nazvanie=value, poryadok=poryadok)
                self.session.add(obj)
                self.session.flush()
                self._razmery[value] = obj.id

        logger.info(f"  Создано {len(self._razmery)} размеров")

    def _migrate_importery(self):
        """Миграция импортеров"""
        logger.info("Миграция импортеров...")
        df = self._load_sheet('Все модели')

        for value in df['Импортер'].dropna().unique():
            value = clean_string(value)
            if value and value not in self._importery:
                # Получаем дополнительные данные
                row = df[df['Импортер'] == value].iloc[0]
                obj = Importer(
                    nazvanie=value,
                    nazvanie_en=clean_string(row.get('Importer')),
                    inn=clean_string(row.get('ИНН')),
                    adres=clean_string(row.get('Адрес импортера'))
                )
                self.session.add(obj)
                self.session.flush()
                self._importery[value] = obj.id

        logger.info(f"  Создано {len(self._importery)} импортеров")

    def _migrate_fabriki(self):
        """Миграция фабрик"""
        logger.info("Миграция фабрик...")
        df = self._load_sheet('Все модели')

        for value in df['Фабрика'].dropna().unique():
            value = clean_string(value)
            if value and value not in self._fabriki:
                row = df[df['Фабрика'] == value].iloc[0]
                obj = Fabrika(
                    nazvanie=value,
                    strana=clean_string(row.get('Страна производства'))
                )
                self.session.add(obj)
                self.session.flush()
                self._fabriki[value] = obj.id

        logger.info(f"  Создано {len(self._fabriki)} фабрик")

    # ============================================
    # ЦВЕТА
    # ============================================

    def _migrate_cveta(self):
        """Миграция цветов"""
        logger.info("Миграция цветов...")
        df = self._load_sheet('Аналитики цветов')

        count = 0
        for _, row in df.iterrows():
            color_code = clean_string(row.get('Color code'))
            if not color_code or color_code in self._cveta:
                continue

            status_name = clean_string(row.get('Статус'))
            status_id = self._statusy.get(status_name) if status_name else None

            obj = Cvet(
                color_code=color_code,
                cvet=clean_string(row.get('Цвет')),
                color=clean_string(row.get('Сolor')),
                lastovica=clean_string(row.get('Gusset')),
                status_id=status_id
            )
            self.session.add(obj)
            self.session.flush()
            self._cveta[color_code] = obj.id
            count += 1

        logger.info(f"  Создано {count} цветов")

    # ============================================
    # МОДЕЛИ ОСНОВА (ВЕРХНИЙ УРОВЕНЬ)
    # ============================================

    def _migrate_modeli_osnova(self):
        """Миграция базовых моделей с характеристиками"""
        logger.info("Миграция моделей основа (с характеристиками)...")
        df = self._load_sheet('Все модели')

        # Фильтруем только главные строки (где есть код в колонке Unnamed: 0)
        df_main = df[df['Unnamed: 0'].notna()]

        # Группируем по модели основе и берём первую строку для характеристик
        for osnova_name in df_main['Модель основа'].dropna().unique():
            osnova_name = clean_string(osnova_name)
            if not osnova_name or osnova_name in self._modeli_osnova:
                continue

            # Берём первую строку этой модели основы для характеристик
            rows = df_main[df_main['Модель основа'] == osnova_name]
            if rows.empty:
                continue

            row = rows.iloc[0]

            # Получаем FK
            kategoriya = clean_string(row.get('Категория'))
            kollekciya = clean_string(row.get('Коллекция'))
            fabrika = clean_string(row.get('Фабрика'))

            obj = ModelOsnova(
                kod=osnova_name,
                kategoriya_id=self._kategorii.get(kategoriya),
                kollekciya_id=self._kollekcii.get(kollekciya),
                fabrika_id=self._fabriki.get(fabrika),

                # Размеры и упаковка
                razmery_modeli=clean_string(row.get('Размеры модели')),
                sku_china=clean_string(row.get('SKU CHINA')),
                upakovka=clean_string(row.get('Упаковка')),
                ves_kg=clean_numeric(row.get('Вес (кг)')),
                dlina_cm=clean_numeric(row.get('Длина')),
                shirina_cm=clean_numeric(row.get('Ширина')),
                vysota_cm=clean_numeric(row.get('Высота')),
                kratnost_koroba=clean_integer(row.get('Кратность короба')),
                srok_proizvodstva=clean_string(row.get('Срок производства')),
                komplektaciya=clean_string(row.get('Комплектация')),

                # Материал и состав
                material=clean_string(row.get('Материал')),
                sostav_syrya=clean_string(row.get('Состав сырья')),
                composition=clean_string(row.get('Composition')),

                # Характеристики
                dlya_kakoy_grudi=clean_string(row.get('Для какой груди')),
                stepen_podderzhki=clean_string(row.get('Степень поддержки груди/в характеристике карточки')),
                forma_chashki=clean_string(row.get('Форма чашки')),
                regulirovka=clean_string(row.get('Регулировка')),
                zastezhka=clean_string(row.get('Застежка')),
                posadka_trusov=clean_string(row.get('Посадка трусов')),
                vid_trusov=clean_string(row.get('Вид трусов')),
                naznachenie=clean_string(row.get('Назначение')),
                stil=clean_string(row.get('Стиль')),
                po_nastroeniyu=clean_string(row.get('По настроению')),

                # Логистика
                tnved=clean_string(row.get('ТНВЭД')),
                gruppa_sertifikata=clean_string(row.get('Группа')),

                # Контент
                nazvanie_etiketka=clean_string(row.get('Название для Этикетки')),
                nazvanie_sayt=clean_string(row.get('Название для сайта')),
                opisanie_sayt=clean_string(row.get('Описание для сайта')),
                details=clean_string(row.get('Details')),
                description=clean_string(row.get('Description')),
                tegi=clean_string(row.get('Теги')),
                notion_link=clean_string(row.get('Ссылка на ноушн'))
            )
            self.session.add(obj)
            self.session.flush()
            self._modeli_osnova[osnova_name] = obj.id

        logger.info(f"  Создано {len(self._modeli_osnova)} моделей основа")

    # ============================================
    # МОДЕЛИ (ВАРИАЦИИ НА ЮРЛИЦАХ)
    # ============================================

    def _migrate_modeli(self):
        """Миграция моделей (вариации на разных юрлицах)"""
        logger.info("Миграция моделей (вариации)...")
        df = self._load_sheet('Все модели')

        count = 0
        for _, row in df.iterrows():
            # ВАЖНО: Фильтруем только главные строки (где есть код в колонке Unnamed: 0)
            kod_modeli = clean_string(row.get('Unnamed: 0'))
            if not kod_modeli:
                continue  # Пропускаем строки размеров

            nazvanie = clean_string(row.get('Название модели'))
            if not nazvanie:
                continue

            # Пропускаем дубликаты по коду модели
            if kod_modeli in self._modeli:
                continue

            # Получаем FK
            model_osnova = clean_string(row.get('Модель основа'))
            status = clean_string(row.get('Статус'))
            importer = clean_string(row.get('Импортер'))

            obj = Model(
                kod=kod_modeli,
                nazvanie=nazvanie,
                nazvanie_en=clean_string(row.get('Name')),
                artikul_modeli=clean_string(row.get('Артикул модели')),
                model_osnova_id=self._modeli_osnova.get(model_osnova),
                importer_id=self._importery.get(importer),
                status_id=self._statusy.get(MODEL_STATUS_MAP.get(status, status)) if status else None,
                nabor=clean_boolean(row.get('Набор')),
                rossiyskiy_razmer=clean_string(row.get('Российский размер'))
            )
            self.session.add(obj)
            self.session.flush()
            self._modeli[kod_modeli] = obj.id

            # Case-insensitive lookup: добавляем lowercase-ключ
            if kod_modeli.lower() not in self._modeli:
                self._modeli[kod_modeli.lower()] = obj.id

            # Также добавляем маппинг по названию для обратной совместимости
            if nazvanie not in self._modeli:
                self._modeli[nazvanie] = obj.id
            if nazvanie.lower() not in self._modeli:
                self._modeli[nazvanie.lower()] = obj.id

            count += 1

        logger.info(f"  Создано {count} моделей")

    # ============================================
    # СКЛЕЙКИ
    # ============================================

    def _migrate_skleyki_wb(self):
        """Миграция склеек WB"""
        logger.info("Миграция склеек WB...")
        df = self._load_sheet('Все товары')

        for value in df['Склейка на WB'].dropna().unique():
            value = clean_string(value)
            if value and value not in self._skleyki_wb:
                # Определяем импортера по названию склейки
                importer_id = None
                if 'ИП' in value:
                    importer_id = self._importery.get('ИП Медведева П.В.')
                elif 'ООО' in value:
                    importer_id = self._importery.get('ООО Вуки')

                obj = SleykaWB(nazvanie=value, importer_id=importer_id)
                self.session.add(obj)
                self.session.flush()
                self._skleyki_wb[value] = obj.id

        logger.info(f"  Создано {len(self._skleyki_wb)} склеек WB")

    # ============================================
    # АРТИКУЛЫ
    # ============================================

    def _migrate_artikuly(self):
        """Миграция артикулов (из листа Все товары)"""
        logger.info("Миграция артикулов...")
        df = self._load_sheet('Все товары')

        count = 0
        for _, row in df.iterrows():
            artikul_code = clean_string(row.get('Артикул'))
            if not artikul_code or artikul_code in self._artikuly:
                continue

            # Находим модель по названию (case-insensitive fallback)
            model_name = clean_string(row.get('Модель'))
            model_id = self._modeli.get(model_name)
            if model_id is None and model_name:
                model_id = self._modeli.get(model_name.lower())

            # Находим цвет по color_code
            color_code = clean_string(row.get('Color code'))
            cvet_id = self._cveta.get(color_code)

            # Статус
            status_name = clean_string(row.get('Статус товара'))
            status_id = self._statusy.get(status_name)

            obj = Artikul(
                artikul=artikul_code,
                model_id=model_id,
                cvet_id=cvet_id,
                status_id=status_id,
                nomenklatura_wb=clean_integer(row.get('Нуменклатура')),
                artikul_ozon=clean_string(row.get('Артикул Ozon'))
            )
            self.session.add(obj)
            self.session.flush()
            self._artikuly[artikul_code] = obj.id
            count += 1

        logger.info(f"  Создано {count} артикулов")

    # ============================================
    # ТОВАРЫ
    # ============================================

    def _migrate_tovary(self):
        """Миграция товаров"""
        logger.info("Миграция товаров...")
        df = self._load_sheet('Все товары')

        count = 0
        errors = 0
        seen_barcodes = set()

        for idx, row in df.iterrows():
            barkod = clean_barcode(row.get('БАРКОД '))
            if not barkod:
                continue

            # Пропускаем дубликаты баркодов
            if barkod in seen_barcodes:
                continue
            seen_barcodes.add(barkod)

            try:
                # Находим артикул
                artikul_code = clean_string(row.get('Артикул'))
                artikul_id = self._artikuly.get(artikul_code)

                # Находим размер
                razmer_name = clean_string(row.get('Размер'))
                razmer_id = self._razmery.get(razmer_name)

                # Статусы
                status_name = clean_string(row.get('Статус товара'))
                status_id = self._statusy.get(status_name)

                status_ozon = clean_string(row.get('Статус товара OZON'))
                status_ozon_id = self._statusy.get(status_ozon)

                obj = Tovar(
                    barkod=barkod,
                    barkod_gs1=clean_barcode(row.get('БАРКОД GS1')),
                    barkod_gs2=clean_barcode(row.get('БАРКОД GS2')),
                    barkod_perehod=clean_barcode(row.get('БАРКОД ПЕРЕХОД')),
                    artikul_id=artikul_id,
                    razmer_id=razmer_id,
                    status_id=status_id,
                    status_ozon_id=status_ozon_id,
                    ozon_product_id=clean_integer(row.get('Ozon Product ID')),
                    ozon_fbo_sku_id=clean_integer(row.get('FBO OZON SKU ID')),
                    lamoda_seller_sku=clean_string(row.get('Seller SKU Lamoda')),
                    sku_china_size=clean_string(row.get('SKU CHINA SIZE'))
                )
                self.session.add(obj)

                # Добавляем связь со склейкой WB
                skleyka_name = clean_string(row.get('Склейка на WB'))
                if skleyka_name and skleyka_name in self._skleyki_wb:
                    self.session.flush()  # Получаем ID товара
                    skleyka = self.session.get(SleykaWB, self._skleyki_wb[skleyka_name])
                    if skleyka:
                        obj.skleyki_wb.append(skleyka)

                count += 1

                # Коммитим партиями по 1000 записей
                if count % 1000 == 0:
                    self.session.flush()
                    logger.info(f"  Обработано {count} товаров...")

            except Exception as e:
                errors += 1
                logger.warning(f"  Ошибка в строке {idx}: {e}")
                continue

        logger.info(f"  Создано {count} товаров, ошибок: {errors}")


def main():
    parser = argparse.ArgumentParser(description='Миграция данных из Excel в PostgreSQL')
    parser.add_argument(
        '--file', '-f',
        default='Спецификации.xlsx',
        help='Путь к файлу Excel (по умолчанию: Спецификации.xlsx)'
    )
    args = parser.parse_args()

    # Определяем путь к файлу
    if os.path.isabs(args.file):
        excel_path = args.file
    else:
        # Относительно папки проекта
        project_root = Path(__file__).parent.parent
        excel_path = project_root / args.file

    if not os.path.exists(excel_path):
        logger.error(f"Файл не найден: {excel_path}")
        sys.exit(1)

    migrator = DataMigrator(str(excel_path))
    migrator.run()


if __name__ == '__main__':
    main()
