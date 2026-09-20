"""Скрипт автоматизированного сбора отзывов с сервиса Otzovik.

Лабораторная работа №1 по курсу «Новые технологии в РПС».
Вариант №9: Сбор отзывов по категориям рейтинга (1–5 звезд).
"""

from __future__ import annotations

import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class DatasetManager:
    """Управление папками датасета, нумерацией и исключением дубликатов."""

    def __init__(
        self,
        base_dir: str = "dataset",
        target_per_class: int = 500
    ) -> None:
        """Инициализация менеджера датасета.

        :param base_dir: Корневая папка для сохранения датасета.
        :param target_per_class: Минимальное количество отзывов на каждый класс.
        """
        self.base_dir = Path(base_dir)
        self.target_per_class = target_per_class
        self.categories: List[int] = [1, 2, 3, 4, 5]
        self._seen_ids: Set[str] = set()
        self._counts: Dict[int, int] = {cat: 0 for cat in self.categories}

        self._init_folders()
        self._sync_with_disk()

    def _init_folders(self) -> None:
        """Программное создание структуры каталогов."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for cat in self.categories:
            folder = self.base_dir / str(cat)
            folder.mkdir(parents=True, exist_ok=True)

    def _sync_with_disk(self) -> None:
        """Подсчет уже имеющихся файлов (защита от потери прогресса)."""
        for cat in self.categories:
            folder = self.base_dir / str(cat)
            if folder.exists():
                txt_files = list(folder.glob("*.txt"))
                self._counts[cat] = len(txt_files)

    def is_quota_filled(self, category: int) -> bool:
        """Проверяет, достигнута ли квота для данной оценки."""
        return self._counts.get(category, 0) >= self.target_per_class

    def is_all_completed(self) -> bool:
        """Проверяет, собраны ли отзывы для всех категорий (1-5)."""
        return all(self.is_quota_filled(cat) for cat in self.categories)

    def save_review(
        self,
        category: int,
        review_id: str,
        title: str,
        text: str,
    ) -> bool:
        """Сохраняет отзыв в файл с именем вида 0000.txt, 0001.txt."""
        if category not in self.categories:
            return False
        if self.is_quota_filled(category):
            return False
        if review_id in self._seen_ids:
            return False

        # Формирование имени файла методом zfill(4) по требованиям задания
        current_idx = self._counts[category]
        file_name = f"{str(current_idx).zfill(4)}.txt"
        file_path = self.base_dir / str(category) / file_name

        payload = f"{title.strip()}\n\n{text.strip()}\n"

        try:
            with open(file_path, "w", encoding="utf-8") as f_out:
                f_out.write(payload)

            self._seen_ids.add(review_id)
            self._counts[category] += 1
            return True
        except OSError as err:
            print(f"[ERROR] Не удалось записать файл {file_path}: {err}")
            return False

    def print_progress(self) -> None:
        """Отображение текущего прогресса сбора данных."""
        progress_str = " | ".join(
            f"★{cat}: {self._counts[cat]}/{self.target_per_class}"
            for cat in self.categories
        )
        print(f"[ПРОГРЕСС] {progress_str}")


class OtzovikScraper:
    """Клиент для обхода страниц и парсинга отзывов с Otzovik."""

    BASE_URL = "https://otzovik.com"

    def __init__(
        self,
        object_slug: str = "sberbank_rossii",
        dataset_manager: Optional[DatasetManager] = None,
        full_text: bool = False,
    ) -> None:
        """Инициализация скрейпера.

        :param object_slug: Идентификатор объекта на Otzovik (из URL).
        :param dataset_manager: Экземпляр DatasetManager.
        :param full_text: Уровень 2 (True - полный текст) или Уровень 1 (False - анонс).
        """
        self.object_slug = object_slug
        self.manager = dataset_manager or DatasetManager()
        self.full_text = full_text

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://otzovik.com/",
        })

    def _fetch_html(self, url: str) -> Optional[str]:
        """Безопасный запрос HTML-страницы с обработкой ошибок."""
        try:
            resp = self.session.get(url, timeout=12)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code in (403, 429):
                print(f"[WARN] Сервер ограничил доступ ({resp.status_code}). Делаем паузу...")
                time.sleep(10)
            else:
                print(f"[WARN] Код ответа сервера: {resp.status_code} для {url}")
        except requests.RequestException as err:
            print(f"[ERROR] Ошибка сети при запросе {url}: {err}")
        return None

    def _parse_rating(self, card: BeautifulSoup) -> Optional[int]:
        """Извлечение количества звезд (1-5) из карточки отзыва."""
        # 1. Поиск по атрибуту title="Общий рейтинг: X"
        score_tag = card.find(attrs={"title": re.compile(r"Общий рейтинг:\s*(\d+)")})
        if score_tag:
            match = re.search(r"Общий рейтинг:\s*(\d+)", score_tag["title"])
            if match:
                return int(match.group(1))

        # 2. Альтернативный поиск по словесным описаниям
        mapping = {
            "Ужасно": 1,
            "Плохо": 2,
            "Средне": 3,
            "Хорошо": 4,
            "Отлично": 5,
        }
        for word, val in mapping.items():
            if card.find(attrs={"title": re.compile(rf"\b{word}\b", re.I)}):
                return val

        return None

    def _fetch_full_review_body(self, review_url: str) -> str:
        """Получение полного текста отзыва со страницы отзыва (Уровень 2)."""
        html = self._fetch_html(review_url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        body_el = soup.find(class_=re.compile(r"review-body|description"))
        if body_el:
            return body_el.get_text("\n", strip=True)
        return ""

    def parse_page(self, page_num: int) -> int:
        """Парсинг одной страницы со списком отзывов.

        :param page_num: Номер страницы (1, 2, ...).
        :return: Количество сохраненных отзывов с этой страницы.
        """
        if page_num == 1:
            url = f"{self.BASE_URL}/reviews/{self.object_slug}/"
        else:
            url = f"{self.BASE_URL}/reviews/{self.object_slug}/{page_num}/"

        print(f"\n[СКАЧИВАНИЕ] Страница {page_num}: {url}")
        html = self._fetch_html(url)
        if not html:
            return 0

        soup = BeautifulSoup(html, "lxml")
        saved_on_page = 0

        # Ищем все ссылки на отзывы на странице
        review_links = soup.find_all("a", href=re.compile(r"/review_\d+\.html"))
        seen_links_on_page: Set[str] = set()

        for r_link in review_links:
            href = r_link.get("href", "")
            if href in seen_links_on_page:
                continue
            seen_links_on_page.add(href)

            # Извлечение уникального ID отзыва
            id_match = re.search(r"/review_(\d+)\.html", href)
            if not id_match:
                continue
            review_id = id_match.group(1)

            # Родительский контейнер всей карточки
            card = r_link.find_parent("div", class_=lambda c: c and "item" in c.split())
            if not card:
                card = r_link.find_parent("div")
            if not card:
                continue

            # Определение рейтинга (1–5)
            rating = self._parse_rating(card)
            if not rating or rating not in (1, 2, 3, 4, 5):
                continue

            # Если квота для этой оценки уже набрана — пропускаем
            if self.manager.is_quota_filled(rating):
                continue

            title = r_link.get_text(strip=True)

            # Текст: Уровень 1 (краткий) или Уровень 2 (полный)
            if self.full_text:
                full_url = urljoin(self.BASE_URL, href)
                # Человеческая пауза перед переходом на полную страницу
                time.sleep(random.uniform(1.2, 2.5))
                text = self._fetch_full_review_body(full_url)
            else:
                body_el = card.find(class_=re.compile(r"review-body|description|review-snip"))
                text = body_el.get_text(" ", strip=True) if body_el else title

            # Сохранение в файл
            if self.manager.save_review(rating, review_id, title, text):
                saved_on_page += 1

        return saved_on_page

    def run(self, max_pages: int = 200) -> None:
        """Основной цикл обхода страниц по пагинации."""
        print(f"=== Старт сбора отзывов по объекту: {self.object_slug} ===")
        self.manager.print_progress()

        for page in range(1, max_pages + 1):
            if self.manager.is_all_completed():
                print("\n[УСПЕХ] Все целевые квоты успешно собраны!")
                break

            saved = self.parse_page(page)
            self.manager.print_progress()

            # Вежливая пауза между страницами (2–4 сек), чтобы сайт не блокировал
            delay = random.uniform(2.0, 4.0)
            print(f"[ИНФО] Найдено и сохранено: {saved}. Пауза {delay:.1f} сек...")
            time.sleep(delay)

        print("\n=== Сбор завершен! Итоговая статистика: ===")
        self.manager.print_progress()


def main() -> None:
    """Точка входа при запуске скрипта."""
    # Для первого тестирования установим цель, например, по 5-10 отзывов на звезду,
    # чтобы быстро убедиться в полной работоспособности.
    # Для полной сдачи лабораторной меняется на 500-1000.
    TARGET_PER_CLASS = 10  # Измените на 500 для полного сбора
    FULL_TEXT_MODE = False  # False = Уровень 1 (быстро), True = Уровень 2

    manager = DatasetManager(base_dir="dataset", target_per_class=TARGET_PER_CLASS)
    scraper = OtzovikScraper(
        object_slug="sberbank_rossii",
        dataset_manager=manager,
        full_text=FULL_TEXT_MODE,
    )
    scraper.run(max_pages=20)


if __name__ == "__main__":
    main()