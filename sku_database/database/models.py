"""
SQLAlchemy модели для базы данных спецификаций товаров Wookiee

ВЕРСИЯ 2.0 - Модель основа как верхний уровень
Все модели имеют русские названия для удобства работы команды.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric, DateTime,
    ForeignKey, Table, BigInteger, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


# ============================================
# ТАБЛИЦЫ СВЯЗЕЙ (Many-to-Many)
# ============================================

# Связь товаров со склейками WB
tovary_skleyki_wb = Table(
    'tovary_skleyki_wb',
    Base.metadata,
    Column('tovar_id', Integer, ForeignKey('tovary.id', ondelete='CASCADE'), primary_key=True),
    Column('skleyka_id', Integer, ForeignKey('skleyki_wb.id', ondelete='CASCADE'), primary_key=True),
    comment='Связь товаров со склейками Wildberries'
)

# Связь товаров со склейками Ozon
tovary_skleyki_ozon = Table(
    'tovary_skleyki_ozon',
    Base.metadata,
    Column('tovar_id', Integer, ForeignKey('tovary.id', ondelete='CASCADE'), primary_key=True),
    Column('skleyka_id', Integer, ForeignKey('skleyki_ozon.id', ondelete='CASCADE'), primary_key=True),
    comment='Связь товаров со склейками Ozon'
)


# ============================================
# 1. СПРАВОЧНИКИ
# ============================================

class Kategoriya(Base):
    """Категории товаров (Комплект белья, Трусы, Боди)"""
    __tablename__ = 'kategorii'
    __table_args__ = {'comment': 'Категории товаров (Комплект белья, Трусы, Боди)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор категории')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название категории')

    # Связи (теперь с modeli_osnova)
    modeli_osnova: Mapped[List['ModelOsnova']] = relationship('ModelOsnova', back_populates='kategoriya')

    def __repr__(self):
        return f"<Kategoriya(id={self.id}, nazvanie='{self.nazvanie}')>"


class Kollekciya(Base):
    """Коллекции (Трикотажное белье, Наборы трусов и т.д.)"""
    __tablename__ = 'kollekcii'
    __table_args__ = {'comment': 'Коллекции (Трикотажное белье, Наборы трусов и т.д.)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор коллекции')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название коллекции')

    # Связи (теперь с modeli_osnova)
    modeli_osnova: Mapped[List['ModelOsnova']] = relationship('ModelOsnova', back_populates='kollekciya')

    def __repr__(self):
        return f"<Kollekciya(id={self.id}, nazvanie='{self.nazvanie}')>"


class Status(Base):
    """Единые статусы (Продается, Выводим, Архив, Подготовка, План, Новый, Запуск)"""
    __tablename__ = 'statusy'
    __table_args__ = {'comment': 'Единые статусы (Продается, Выводим, Архив, Подготовка, План, Новый, Запуск)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор статуса')
    nazvanie: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment='Название статуса')

    def __repr__(self):
        return f"<Status(id={self.id}, nazvanie='{self.nazvanie}')>"


class Razmer(Base):
    """Справочник размеров одежды"""
    __tablename__ = 'razmery'
    __table_args__ = {'comment': 'Справочник размеров одежды'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор размера')
    nazvanie: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, comment='Размер (XS, S, M, L, XL, XXL)')
    poryadok: Mapped[int] = mapped_column(Integer, default=0, comment='Порядок сортировки')

    # Связи
    tovary: Mapped[List['Tovar']] = relationship('Tovar', back_populates='razmer')

    def __repr__(self):
        return f"<Razmer(id={self.id}, nazvanie='{self.nazvanie}')>"


class Importer(Base):
    """Импортеры (юридические лица)"""
    __tablename__ = 'importery'
    __table_args__ = {'comment': 'Импортеры (юридические лица)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор импортера')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название')
    nazvanie_en: Mapped[Optional[str]] = mapped_column(String(100), comment='Название на английском')
    inn: Mapped[Optional[str]] = mapped_column(String(20), comment='ИНН')
    adres: Mapped[Optional[str]] = mapped_column(Text, comment='Адрес импортера')

    # Связи
    modeli: Mapped[List['Model']] = relationship('Model', back_populates='importer')
    skleyki_wb: Mapped[List['SleykaWB']] = relationship('SleykaWB', back_populates='importer')
    skleyki_ozon: Mapped[List['SleykaOzon']] = relationship('SleykaOzon', back_populates='importer')

    def __repr__(self):
        return f"<Importer(id={self.id}, nazvanie='{self.nazvanie}')>"


class Fabrika(Base):
    """Фабрики-производители"""
    __tablename__ = 'fabriki'
    __table_args__ = {'comment': 'Фабрики-производители'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор фабрики')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название фабрики')
    strana: Mapped[Optional[str]] = mapped_column(String(50), comment='Страна производства')

    # Связи (теперь с modeli_osnova)
    modeli_osnova: Mapped[List['ModelOsnova']] = relationship('ModelOsnova', back_populates='fabrika')

    def __repr__(self):
        return f"<Fabrika(id={self.id}, nazvanie='{self.nazvanie}')>"


# ============================================
# 2. ЦВЕТА
# ============================================

class Cvet(Base):
    """Справочник цветов (из Аналитики цветов)"""
    __tablename__ = 'cveta'
    __table_args__ = {'comment': 'Справочник цветов (из Аналитики цветов)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор цвета')
    color_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment='Код цвета')
    cvet: Mapped[Optional[str]] = mapped_column(String(200), comment='Цвет на русском')
    color: Mapped[Optional[str]] = mapped_column(String(200), comment='Color на английском')
    lastovica: Mapped[Optional[str]] = mapped_column(String(50), comment='Цвет ластовицы (Gusset)')
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('statusy.id'), comment='Статус цвета')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    status: Mapped[Optional['Status']] = relationship('Status')
    artikuly: Mapped[List['Artikul']] = relationship('Artikul', back_populates='cvet')

    def __repr__(self):
        return f"<Cvet(id={self.id}, color_code='{self.color_code}', cvet='{self.cvet}')>"


# ============================================
# 3. МОДЕЛИ ОСНОВА (ВЕРХНИЙ УРОВЕНЬ)
# Хранит ВСЕ общие характеристики товара
# ============================================

class ModelOsnova(Base):
    """Базовые модели (Vuki, Moon, Ruby...) - ВЕРХНИЙ УРОВЕНЬ с характеристиками"""
    __tablename__ = 'modeli_osnova'
    __table_args__ = {'comment': 'Базовые модели (Vuki, Moon, Ruby...) - ВЕРХНИЙ УРОВЕНЬ с характеристиками товара'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор базовой модели')
    kod: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment='Код модели основы')

    # Классификация
    kategoriya_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('kategorii.id'), comment='Категория')
    kollekciya_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('kollekcii.id'), comment='Коллекция')
    fabrika_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('fabriki.id'), comment='Фабрика')

    # Размеры и упаковка
    razmery_modeli: Mapped[Optional[str]] = mapped_column(String(50), comment='Размеры модели (S, M, L, XL)')
    sku_china: Mapped[Optional[str]] = mapped_column(String(100), comment='SKU CHINA')
    upakovka: Mapped[Optional[str]] = mapped_column(String(100), comment='Упаковка')
    ves_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 3), comment='Вес (кг)')
    dlina_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), comment='Длина (см)')
    shirina_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), comment='Ширина (см)')
    vysota_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 1), comment='Высота (см)')
    kratnost_koroba: Mapped[Optional[int]] = mapped_column(Integer, comment='Кратность короба')
    srok_proizvodstva: Mapped[Optional[str]] = mapped_column(String(50), comment='Срок производства')
    komplektaciya: Mapped[Optional[str]] = mapped_column(Text, comment='Комплектация')

    # Материал и состав
    material: Mapped[Optional[str]] = mapped_column(String(200), comment='Материал')
    sostav_syrya: Mapped[Optional[str]] = mapped_column(Text, comment='Состав сырья')
    composition: Mapped[Optional[str]] = mapped_column(Text, comment='Composition (английский)')

    # Характеристики товара
    dlya_kakoy_grudi: Mapped[Optional[str]] = mapped_column(String(200), comment='Для какой груди')
    stepen_podderzhki: Mapped[Optional[str]] = mapped_column(String(200), comment='Степень поддержки груди')
    forma_chashki: Mapped[Optional[str]] = mapped_column(String(200), comment='Форма чашки')
    regulirovka: Mapped[Optional[str]] = mapped_column(String(200), comment='Регулировка')
    zastezhka: Mapped[Optional[str]] = mapped_column(String(200), comment='Застежка')
    posadka_trusov: Mapped[Optional[str]] = mapped_column(String(200), comment='Посадка трусов')
    vid_trusov: Mapped[Optional[str]] = mapped_column(String(200), comment='Вид трусов')
    naznachenie: Mapped[Optional[str]] = mapped_column(String(200), comment='Назначение')
    stil: Mapped[Optional[str]] = mapped_column(String(200), comment='Стиль')
    po_nastroeniyu: Mapped[Optional[str]] = mapped_column(String(200), comment='По настроению')

    # Тип коллекции (добавлено миграцией 001)
    tip_kollekcii: Mapped[Optional[str]] = mapped_column(
        String(30),
        comment='Тип коллекции (Трикотажное белье, Бесшовное белье Jelly, Бесшовное белье Audrey)'
    )

    # Логистика и сертификация
    tnved: Mapped[Optional[str]] = mapped_column(String(20), comment='ТНВЭД')
    gruppa_sertifikata: Mapped[Optional[str]] = mapped_column(String(50), comment='Группа сертификата')

    # Контент (общий для всех вариаций)
    nazvanie_etiketka: Mapped[Optional[str]] = mapped_column(String(200), comment='Название для этикетки')
    nazvanie_sayt: Mapped[Optional[str]] = mapped_column(String(200), comment='Название для сайта')
    opisanie_sayt: Mapped[Optional[str]] = mapped_column(Text, comment='Описание для сайта')
    details: Mapped[Optional[str]] = mapped_column(Text, comment='Details (детали на английском)')
    description: Mapped[Optional[str]] = mapped_column(Text, comment='Description (описание на английском)')
    tegi: Mapped[Optional[str]] = mapped_column(Text, comment='Теги')
    notion_link: Mapped[Optional[str]] = mapped_column(String(500), comment='Ссылка на Notion')

    # Служебные поля
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    kategoriya: Mapped[Optional['Kategoriya']] = relationship('Kategoriya', back_populates='modeli_osnova')
    kollekciya: Mapped[Optional['Kollekciya']] = relationship('Kollekciya', back_populates='modeli_osnova')
    fabrika: Mapped[Optional['Fabrika']] = relationship('Fabrika', back_populates='modeli_osnova')
    modeli: Mapped[List['Model']] = relationship('Model', back_populates='model_osnova')

    def __repr__(self):
        return f"<ModelOsnova(id={self.id}, kod='{self.kod}')>"


# ============================================
# 4. МОДЕЛИ (ВАРИАЦИИ НА РАЗНЫХ ЮРЛИЦАХ)
# Хранит только специфику импортера/юрлица
# ============================================

class Model(Base):
    """Модели товаров - вариации на разных юрлицах (Vuki-ИП, Vuki2-ООО)"""
    __tablename__ = 'modeli'
    __table_args__ = {'comment': 'Модели товаров - вариации на разных юрлицах (Vuki-ИП, Vuki2-ООО)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор модели')

    # Код и название вариации
    kod: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, comment='Код вариации (Vuki, VukiN, Vuki2...)')
    nazvanie: Mapped[str] = mapped_column(String(100), nullable=False, comment='Название модели')
    nazvanie_en: Mapped[Optional[str]] = mapped_column(String(100), comment='Name (английское название)')
    artikul_modeli: Mapped[Optional[str]] = mapped_column(String(100), comment='Артикул модели')

    # Связь с основой
    model_osnova_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('modeli_osnova.id'), comment='Модель основа')

    # Специфика юрлица
    importer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('importery.id'), comment='Импортер/юрлицо')
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('statusy.id'), comment='Статус модели')
    nabor: Mapped[bool] = mapped_column(Boolean, default=False, comment='Набор (да/нет)')
    rossiyskiy_razmer: Mapped[Optional[str]] = mapped_column(String(50), comment='Российский размер')

    # Служебные поля
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    model_osnova: Mapped[Optional['ModelOsnova']] = relationship('ModelOsnova', back_populates='modeli')
    importer: Mapped[Optional['Importer']] = relationship('Importer', back_populates='modeli')
    status: Mapped[Optional['Status']] = relationship('Status')
    artikuly: Mapped[List['Artikul']] = relationship('Artikul', back_populates='model')

    def __repr__(self):
        return f"<Model(id={self.id}, kod='{self.kod}', nazvanie='{self.nazvanie}')>"


# ============================================
# 5. СКЛЕЙКИ МАРКЕТПЛЕЙСОВ
# ============================================

class SleykaWB(Base):
    """Склейки Wildberries - группировка карточек товаров на WB"""
    __tablename__ = 'skleyki_wb'
    __table_args__ = {'comment': 'Склейки Wildberries - группировка карточек товаров на WB'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор склейки')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название склейки')
    importer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('importery.id'), comment='Импортер')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    importer: Mapped[Optional['Importer']] = relationship('Importer', back_populates='skleyki_wb')
    tovary: Mapped[List['Tovar']] = relationship('Tovar', secondary=tovary_skleyki_wb, back_populates='skleyki_wb')

    def __repr__(self):
        return f"<SleykaWB(id={self.id}, nazvanie='{self.nazvanie}')>"


class SleykaOzon(Base):
    """Склейки Ozon - группировка карточек товаров на Ozon"""
    __tablename__ = 'skleyki_ozon'
    __table_args__ = {'comment': 'Склейки Ozon - группировка карточек товаров на Ozon'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор склейки')
    nazvanie: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Название склейки')
    importer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('importery.id'), comment='Импортер')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    importer: Mapped[Optional['Importer']] = relationship('Importer', back_populates='skleyki_ozon')
    tovary: Mapped[List['Tovar']] = relationship('Tovar', secondary=tovary_skleyki_ozon, back_populates='skleyki_ozon')

    def __repr__(self):
        return f"<SleykaOzon(id={self.id}, nazvanie='{self.nazvanie}')>"


# ============================================
# 6. АРТИКУЛЫ (Модель + Цвет)
# ============================================

class Artikul(Base):
    """Артикулы (модель в конкретном цвете)"""
    __tablename__ = 'artikuly'
    __table_args__ = {'comment': 'Артикулы (модель в конкретном цвете)'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор артикула')
    artikul: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment='Артикул')
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('modeli.id'), comment='Модель')
    cvet_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('cveta.id'), comment='Цвет')
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('statusy.id'), comment='Статус')
    nomenklatura_wb: Mapped[Optional[int]] = mapped_column(BigInteger, comment='Номенклатура WB')
    artikul_ozon: Mapped[Optional[str]] = mapped_column(String(50), comment='Артикул Ozon')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    model: Mapped[Optional['Model']] = relationship('Model', back_populates='artikuly')
    cvet: Mapped[Optional['Cvet']] = relationship('Cvet', back_populates='artikuly')
    status: Mapped[Optional['Status']] = relationship('Status')
    tovary: Mapped[List['Tovar']] = relationship('Tovar', back_populates='artikul')

    def __repr__(self):
        return f"<Artikul(id={self.id}, artikul='{self.artikul}')>"


# ============================================
# 7. ТОВАРЫ/SKU
# ============================================

class Tovar(Base):
    """Товары/SKU (из листа 'Все товары') - конкретные баркоды"""
    __tablename__ = 'tovary'
    __table_args__ = {'comment': 'Товары/SKU (из листа "Все товары") - конкретные баркоды'}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор товара')

    # Баркоды
    barkod: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment='Основной баркод')
    barkod_gs1: Mapped[Optional[str]] = mapped_column(String(20), comment='БАРКОД GS1')
    barkod_gs2: Mapped[Optional[str]] = mapped_column(String(20), comment='БАРКОД GS2')
    barkod_perehod: Mapped[Optional[str]] = mapped_column(String(20), comment='БАРКОД ПЕРЕХОД')

    # Связи FK
    artikul_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('artikuly.id'), comment='Артикул')
    razmer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('razmery.id'), comment='Размер')

    # Статусы по каналам
    status_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('statusy.id'), comment='Статус товара (общий)')
    status_ozon_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('statusy.id'), comment='Статус товара OZON')

    # Идентификаторы маркетплейсов
    ozon_product_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='Ozon Product ID')
    ozon_fbo_sku_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='FBO OZON SKU ID')
    lamoda_seller_sku: Mapped[Optional[str]] = mapped_column(String(50), comment='Seller SKU Lamoda')
    sku_china_size: Mapped[Optional[str]] = mapped_column(String(50), comment='SKU CHINA SIZE')

    # Служебные поля
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Дата создания')
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment='Дата обновления')

    # Связи
    artikul: Mapped[Optional['Artikul']] = relationship('Artikul', back_populates='tovary')
    razmer: Mapped[Optional['Razmer']] = relationship('Razmer', back_populates='tovary')
    status: Mapped[Optional['Status']] = relationship('Status', foreign_keys=[status_id])
    status_ozon: Mapped[Optional['Status']] = relationship('Status', foreign_keys=[status_ozon_id])
    skleyki_wb: Mapped[List['SleykaWB']] = relationship('SleykaWB', secondary=tovary_skleyki_wb, back_populates='tovary')
    skleyki_ozon: Mapped[List['SleykaOzon']] = relationship('SleykaOzon', secondary=tovary_skleyki_ozon, back_populates='tovary')

    def __repr__(self):
        return f"<Tovar(id={self.id}, barkod='{self.barkod}')>"


# ============================================
# 8. ИСТОРИЯ ИЗМЕНЕНИЙ
# ============================================

class IstoriyaIzmeneniy(Base):
    """История изменений - журнал всех изменений в спецификациях"""
    __tablename__ = 'istoriya_izmeneniy'
    __table_args__ = (
        CheckConstraint("tip_operacii IN ('INSERT', 'UPDATE', 'DELETE')", name='check_tip_operacii'),
        {'comment': 'История изменений - журнал всех изменений в спецификациях'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Идентификатор записи')
    tablica: Mapped[str] = mapped_column(String(50), nullable=False, comment='Название таблицы')
    zapis_id: Mapped[int] = mapped_column(Integer, nullable=False, comment='ID измененной записи')
    pole: Mapped[Optional[str]] = mapped_column(String(100), comment='Название поля')
    staroe_znachenie: Mapped[Optional[str]] = mapped_column(Text, comment='Старое значение')
    novoe_znachenie: Mapped[Optional[str]] = mapped_column(Text, comment='Новое значение')
    tip_operacii: Mapped[str] = mapped_column(String(20), nullable=False, comment='Тип: INSERT/UPDATE/DELETE')
    polzovatel: Mapped[Optional[str]] = mapped_column(String(100), comment='Кто изменил')
    data_izmeneniya: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment='Когда изменено')

    def __repr__(self):
        return f"<IstoriyaIzmeneniy(id={self.id}, tablica='{self.tablica}', tip='{self.tip_operacii}')>"
