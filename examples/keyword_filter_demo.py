"""
Demo script for keyword filtering functionality.

This script demonstrates the usage of text normalization and keyword matching
implemented in Epic 3.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.domain.entities import FilterConfig, FilterMode, KeywordOptions, Language
from app.filters.keyword_matcher import (
    evaluate_filter_keywords,
    get_match_score,
    highlight_keywords,
    match_filter_keywords,
    match_keywords_in_text,
)
from app.nlp.preprocess import normalize_text


def demo_text_normalization():
    """Demonstrate text normalization capabilities."""
    print("=" * 80)
    print("DEMO 1: Text Normalization")
    print("=" * 80)

    texts = [
        "Привет! Проверьте наш канал: https://t.me/example 🚀",
        "Python is a GREAT programming language! 🐍",
        "Изучаю программирование на Python и JavaScript",
    ]

    for text in texts:
        print(f"\nOriginal: {text}")
        result = normalize_text(
            text,
            language=Language.AUTO,
            remove_urls=True,
            remove_emojis_flag=True,
            use_lemmatization=False,  # Disable for faster demo
            use_nltk_tokenizer=False,
        )
        print(f"Normalized: {result.normalized}")
        print(f"Tokens: {result.tokens}")
        print(f"Language: {result.language}")
        print(f"Empty: {result.is_empty}")


def demo_keyword_matching():
    """Demonstrate keyword matching."""
    print("\n" + "=" * 80)
    print("DEMO 2: Keyword Matching")
    print("=" * 80)

    test_cases = [
        {
            "text": "Python is a great programming language for beginners",
            "keywords": ["python", "programming"],
            "options": KeywordOptions(case_sensitive=False, use_lemmatization=False),
        },
        {
            "text": "Изучаю программирование на Python и его возможности",
            "keywords": ["python", "программирование", "java"],
            "options": KeywordOptions(
                case_sensitive=False, language=Language.RUSSIAN, use_lemmatization=False
            ),
        },
        {
            "text": "Python Programming Language",
            "keywords": ["python", "programming"],
            "options": KeywordOptions(case_sensitive=True, use_lemmatization=False),
        },
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Text: {case['text']}")
        print(f"Keywords: {case['keywords']}")
        print(f"Options: case_sensitive={case['options'].case_sensitive}")

        match = match_keywords_in_text(
            case["text"], case["keywords"], options=case["options"]
        )

        print(f"Matched: {match.has_match}")
        print(f"Found keywords: {match.matched_keywords}")
        print(f"Match count: {match.match_count}")

        if match.has_match:
            score = get_match_score(match)
            print(f"Score: {score:.3f}")


def demo_filter_evaluation():
    """Demonstrate filter configuration and evaluation."""
    print("\n" + "=" * 80)
    print("DEMO 3: Filter Evaluation")
    print("=" * 80)

    # Test case 1: Any keyword matches
    print("\n--- Filter 1: Any keyword (OR logic) ---")
    config1 = FilterConfig(
        mode=FilterMode.KEYWORD_ONLY,
        keywords=["python", "javascript", "java"],
        require_all_keywords=False,
        keyword_options=KeywordOptions(case_sensitive=False, use_lemmatization=False),
    )

    texts1 = [
        "I love Python programming",
        "JavaScript is also great",
        "Ruby is my favorite",
    ]

    for text in texts1:
        matches = evaluate_filter_keywords(text, config1)
        print(f"'{text}' -> {matches}")

    # Test case 2: All keywords required
    print("\n--- Filter 2: All keywords (AND logic) ---")
    config2 = FilterConfig(
        mode=FilterMode.KEYWORD_ONLY,
        keywords=["python", "programming", "language"],
        require_all_keywords=True,
        keyword_options=KeywordOptions(case_sensitive=False, use_lemmatization=False),
    )

    texts2 = [
        "Python is a programming language",
        "Python is a great programming tool",
        "I love programming in Python",
    ]

    for text in texts2:
        matches = evaluate_filter_keywords(text, config2)
        match_result = match_filter_keywords(text, config2)
        print(
            f"'{text}' -> {matches} (found: {match_result.matched_keywords})"
        )

    # Test case 3: Whole word matching
    print("\n--- Filter 3: Whole word matching ---")
    config3 = FilterConfig(
        mode=FilterMode.KEYWORD_ONLY,
        keywords=["python"],
        keyword_options=KeywordOptions(
            case_sensitive=False, whole_word=True, use_lemmatization=False
        ),
    )

    texts3 = [
        "Python is great",
        "pythonic code style",
        "micropython for embedded",
    ]

    for text in texts3:
        matches = evaluate_filter_keywords(text, config3)
        print(f"'{text}' -> {matches}")


def demo_keyword_highlighting():
    """Demonstrate keyword highlighting."""
    print("\n" + "=" * 80)
    print("DEMO 4: Keyword Highlighting")
    print("=" * 80)

    text = "Python is a powerful programming language. Many developers love Python."
    keywords = ["python", "programming"]

    print(f"\nOriginal text:\n{text}")

    match = match_keywords_in_text(text, keywords)
    if match.has_match:
        # Default markdown highlighting
        highlighted1 = highlight_keywords(text, match)
        print(f"\nMarkdown style:\n{highlighted1}")

        # HTML highlighting
        highlighted2 = highlight_keywords(text, match, highlight_format="<mark>{keyword}</mark>")
        print(f"\nHTML style:\n{highlighted2}")


def demo_russian_text():
    """Demonstrate Russian text processing."""
    print("\n" + "=" * 80)
    print("DEMO 5: Russian Text Processing")
    print("=" * 80)

    config = FilterConfig(
        mode=FilterMode.KEYWORD_ONLY,
        keywords=["python", "программирование", "разработка"],
        require_all_keywords=False,
        keyword_options=KeywordOptions(
            case_sensitive=False, language=Language.RUSSIAN, use_lemmatization=False
        ),
    )

    russian_texts = [
        "Программирование на Python - это просто и увлекательно",
        "Разработка веб-приложений с использованием Django",
        "Python используется в машинном обучении",
        "Изучение Java и C++ для начинающих",
    ]

    print(f"Filter keywords: {config.keywords}")
    print(f"Mode: {config.mode}")
    print(f"Require all: {config.require_all_keywords}\n")

    for text in russian_texts:
        match_result = match_filter_keywords(text, config)
        matches = evaluate_filter_keywords(text, config)
        score = get_match_score(match_result)

        print(f"Text: {text}")
        print(f"  Matches: {matches}")
        print(f"  Found: {match_result.matched_keywords}")
        print(f"  Score: {score:.3f}")
        print()


def demo_multi_word_phrases():
    """Demonstrate multi-word phrase matching."""
    print("\n" + "=" * 80)
    print("DEMO 6: Multi-word Phrase Matching")
    print("=" * 80)

    config = FilterConfig(
        mode=FilterMode.KEYWORD_ONLY,
        keywords=["machine learning", "data science", "artificial intelligence"],
        keyword_options=KeywordOptions(case_sensitive=False, use_lemmatization=False),
    )

    texts = [
        "Machine learning is a subset of artificial intelligence",
        "I work in data science and machine learning",
        "Learning about machines and artificial stuff",
        "Data science helps in making data-driven decisions",
    ]

    print(f"Looking for phrases: {config.keywords}\n")

    for text in texts:
        match_result = match_filter_keywords(text, config)
        print(f"Text: {text}")
        print(f"  Found: {match_result.matched_keywords}")
        print(f"  Match count: {match_result.match_count}")
        print()


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "KEYWORD FILTER DEMO - EPIC 3" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")

    try:
        demo_text_normalization()
        demo_keyword_matching()
        demo_filter_evaluation()
        demo_keyword_highlighting()
        demo_russian_text()
        demo_multi_word_phrases()

        print("\n" + "=" * 80)
        print("All demos completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
