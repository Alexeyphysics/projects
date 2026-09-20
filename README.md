cat << 'EOF' > README.md
# Лабораторная работа №1. Автоматизированный сбор данных (Web-scraping)

**Дисциплина:** Новые технологии в РПС  
**Вариант 9:** Сбор отзывов с сервиса *Otzovik* (рейтинги 1–5 звезд).

## Структура проекта
- `scraper.py` — основной исполняемый python-скрипт сбора данных.
- `lab1_notebook.ipynb` — интерактивный jupyter-ноутбук (Google Colab).
- `requirements.txt` — список зависимостей.
- `dataset/` — каталог с собранными текстовыми отзывами по подпапкам `1/` ... `5/`.

## Установка и запуск
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 scraper.py