# Эпик 4: Семантический поиск (embeddings + semantic matcher)

## Что сделано

- Добавлен модуль эмбеддингов `app/nlp/embeddings.py` на базе `sentence-transformers`.
- Реализовано кэширование эмбеддингов в памяти (один общий cache для текстов сообщений и тем фильтров).
- Реализован семантический матчинг `app/filters/semantic_matcher.py`:
  - расчёт косинусного сходства (для нормализованных эмбеддингов — это dot-product)
  - поддержка порога (threshold)
  - матчинг 1 текст ↔ 1 тема, 1 текст ↔ N тем, batch (N текстов ↔ M тем)
  - утилиты: подготовка тем, поиск похожих тем, ранжирование по скору
- Добавлены unit-тесты:
  - `app/tests/unit/test_embeddings.py` — **офлайновый** (модель замокана)
  - `app/tests/unit/test_semantic_matcher.py` — **офлайновый** (замоканы эмбеддинги)

## Конфигурация

Настройки уже есть в `app/config/settings.py` (секция `FilterSettings`):

- `FILTER_ENABLE_SEMANTIC` (bool, default true)
- `FILTER_SEMANTIC_THRESHOLD` (float 0..1, default 0.7)
- `FILTER_EMBEDDING_MODEL` (str, default `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)
- `FILTER_EMBEDDING_CACHE_SIZE` (int, default 1000)

> Примечание: порог в рантайме для конкретного фильтра берётся из `FilterConfig.semantic_options.threshold`.

## Кэширование

- Кэш находится в памяти процесса (`_EMBEDDING_CACHE: dict[str, np.ndarray]`).
- Ключ кэша = `{model_name}:{md5(text)}`.
- В `semantic_matcher.match_text_to_topics(..., use_cache=True)` темы кодируются через `encode_texts_cached()`.

## Текущий статус «живой» проверки семантики

Код семантики реализован и покрыт тестами, но «живая» проверка на реальной модели **зависит от скачивания весов HuggingFace**.

Сейчас в окружении видно:
- попытка скачать модель упирается в `ReadTimeout` к `huggingface.co`
- при ожидании скачивания/локов процесс можно прервать (Ctrl+C), и тогда эмбеддинги не успевают посчитаться

Чтобы проверить реальную модель:

1) Запускать из `venv` (а не из conda/base)
2) Убедиться, что есть доступ в интернет
3) Увеличить таймауты huggingface при первом скачивании (пример):

```bash
export HF_HUB_READ_TIMEOUT=60
export HF_HUB_CONNECT_TIMEOUT=30
python -c "from app.nlp.embeddings import encode_text; print(encode_text('Привет'))"
```

После первого успешного скачивания модель будет использовать локальный cache.

## Файлы

- `app/nlp/embeddings.py`
- `app/filters/semantic_matcher.py`
- `app/tests/unit/test_embeddings.py`
- `app/tests/unit/test_semantic_matcher.py`

## Проверка

```bash
pytest -q
```

На момент завершения эпика: `109 passed`.
