"""Скрипт для автоматизированного сбора отзывов с сервиса Otzovik.

Лабораторная работа №1 по курсу «Новые технологии в РПС».
Вариант №9: Сбор отзывов по категориям рейтинга (1-5 звезд).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Set


class DatasetManager:
    """Класс для управления структурой датасета и сохранения файлов.

    Отвечает за программное создание папок, дедупликацию и
    форматирование имен файлов с ведущими нулями (PEP8).
    """

    def __init__(self, base_dir: str = "dataset", target_count: int = 1000) -> None:
        """Инициализация менеджера датасета.

        :param base_dir: Корневая папка датасета.
        :param target_count: Целевое количество отзывов для каждого класса.
        """
        self.base_dir = Path(base_dir)
        self.target_count = target_count
        self.categories: list[int] = [1, 2, 3, 4, 5]
        self._seen_ids: Set[str] = set()
        self._counts: Dict[int, int] = {cat: 0 for cat in self.categories}

        self._init_folders()
        self._sync_existing_data()

    def _init_folders(self) -> None:
        """Программное создание структуры каталогов.

        Ручное создание папок запрещено требованиями лабораторной.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for cat in self.categories:
            cat_folder = self.base_dir / str(cat)
            cat_folder.mkdir(parents=True, exist_ok=True)

    def _sync_existing_data(self) -> None:
        """Синхронизация счетчиков с уже существующими файлами на диске.

        Позволяет возобновлять парсинг без перезаписи существующих данных.
        """
        for cat in self.categories:
            cat_folder = self.base_dir / str(cat)
            if cat_folder.exists():
                existing_files = list(cat_folder.glob("*.txt"))
                self._counts[cat] = len(existing_files)

    def is_quota_reached(self, category: int) -> bool:
        """Проверяет, набрана ли квота отзывов для конкретной звезды."""
        return self._counts.get(category, 0) >= self.target_count

    def is_all_completed(self) -> bool:
        """Проверяет, собраны ли все отзывы для всех 5 звезд."""
        return all(self.is_quota_reached(cat) for cat in self.categories)

    def is_duplicate(self, review_id: str) -> bool:
        """Проверяет, был ли данный отзыв уже обработан."""
        return review_id in self._seen_ids

    def save_review(
        self,
        category: int,
        review_id: str,
        title: str,
        text: str,
    ) -> bool:
        """Сохраняет отзыв в отдельный текстовый файл.

        Имя файла генерируется с ведущими нулями с помощью метода `str.zfill()`.

        :param category: Оценка отзыва (1-5).
        :param review_id: Уникальный ID отзыва для дедупликации.
        :param title: Заголовок отзыва.
        :param text: Текст отзыва.
        :return: True, если отзыв успешно сохранен, False в противном случае.
        """
        if category not in self.categories:
            return False

        if self.is_quota_reached(category):
            return False

        if self.is_duplicate(review_id):
            return False

        # Формирование имени файла: 0000.txt, 0001.txt и т.д.
        current_index = self._counts[category]
        file_name = f"{str(current_index).zfill(4)}.txt"
        file_path = self.base_dir / str(category) / file_name

        content = f"{title.strip()}\n\n{text.strip()}\n"

        try:
            with open(file_path, "w", encoding="utf-8") as file_handler:
                file_handler.write(content)

            self._seen_ids.add(review_id)
            self._counts[category] += 1
            return True
        except OSError as error:
            print(f"[ERROR] Ошибка записи в файл {file_path}: {error}")
            return False

    def get_stats(self) -> Dict[int, int]:
        """Возвращает текущую статистику собранных файлов по категориям."""
        return self._counts.copy()


if __name__ == "__main__":
    # Быстрый самотест для проверки логики и создания папок
    manager = DatasetManager(base_dir="dataset", target_count=5)
    print("Инициализация прошла успешно!")
    print("Текущая статистика:", manager.get_stats())
