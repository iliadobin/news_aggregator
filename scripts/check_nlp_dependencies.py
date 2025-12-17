#!/usr/bin/env python3
"""
Script to check if all NLP dependencies are installed and configured correctly.

This script verifies:
- Required Python packages are installed
- NLTK data is downloaded
- pymorphy2 dictionaries are available
- Basic functionality works
"""

import sys
import zipfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_package(package_name: str, import_name: str = None) -> bool:
    """
    Check if a package is installed.

    Args:
        package_name: Name of the package (for display)
        import_name: Import name if different from package name

    Returns:
        True if package is available, False otherwise
    """
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
        print(f"✅ {package_name} is installed")
        return True
    except ImportError:
        print(f"❌ {package_name} is NOT installed")
        return False


def check_nltk_data() -> bool:
    """
    Check if required NLTK data is downloaded.

    Returns:
        True if all required data is available
    """
    try:
        import nltk

        required_data = [
            ("tokenizers/punkt", "punkt tokenizer"),
            ("corpora/wordnet", "wordnet"),
            ("corpora/omw-1.4", "omw-1.4"),
        ]

        all_ok = True
        for data_path, data_name in required_data:
            try:
                nltk.data.find(data_path)
                print(f"✅ NLTK {data_name} is available")
            except LookupError:
                print(f"⚠️  NLTK {data_name} is NOT downloaded (will auto-download on first use)")
                all_ok = False
            except zipfile.BadZipFile:
                # NLTK sometimes encounters a corrupted zip in its search paths;
                # we shouldn't crash the dependency checker because of that.
                print(
                    f"⚠️  NLTK {data_name}: found a corrupted zip in NLTK data paths "
                    f"(BadZipFile). Consider clearing your NLTK data directory and re-downloading."
                )
                all_ok = False
            except OSError as e:
                # Defensive: filesystem issues or broken path entries shouldn't crash the check.
                print(f"⚠️  NLTK {data_name}: error while checking NLTK data ({e!r})")
                all_ok = False
            except Exception as e:
                print(f"⚠️  NLTK {data_name}: unexpected error while checking ({e!r})")
                all_ok = False

        return all_ok
    except ImportError:
        print("⚠️  NLTK is not installed, skipping data check")
        return False


def check_pymorphy2() -> bool:
    """
    Check if pymorphy2 and Russian dictionaries are available.

    Returns:
        True if pymorphy2 works correctly
    """
    try:
        import pymorphy3

        morph = pymorphy3.MorphAnalyzer(lang="ru")
        # Test basic functionality
        parsed = morph.parse("программирование")[0]
        lemma = parsed.normal_form
        print(f"✅ pymorphy3 is working (test: программирование -> {lemma})")
        return True
    except ImportError:
        print("❌ pymorphy3 is NOT installed")
        return False
    except Exception as e:
        print(f"❌ pymorphy3 error: {e}")
        return False


def test_text_normalization() -> bool:
    """
    Test basic text normalization functionality.

    Returns:
        True if normalization works
    """
    try:
        from app.nlp.preprocess import normalize_text
        from app.domain.entities import Language

        text = "Hello World! This is a TEST."
        result = normalize_text(
            text,
            language=Language.AUTO,
            use_lemmatization=False,
            use_nltk_tokenizer=False,
        )

        if result.normalized and result.tokens:
            print(f"✅ Text normalization works")
            print(f"   Original: {text}")
            print(f"   Normalized: {result.normalized}")
            print(f"   Tokens: {result.tokens[:3]}...")
            return True
        else:
            print(f"❌ Text normalization failed")
            return False
    except Exception as e:
        print(f"❌ Text normalization error: {e}")
        return False


def test_keyword_matching() -> bool:
    """
    Test basic keyword matching functionality.

    Returns:
        True if keyword matching works
    """
    try:
        from app.filters.keyword_matcher import match_keywords_in_text

        text = "Python is a great programming language"
        keywords = ["python", "programming"]

        match = match_keywords_in_text(text, keywords)

        if match.has_match and len(match.matched_keywords) == 2:
            print(f"✅ Keyword matching works")
            print(f"   Text: {text}")
            print(f"   Keywords: {keywords}")
            print(f"   Found: {match.matched_keywords}")
            return True
        else:
            print(f"❌ Keyword matching failed")
            return False
    except Exception as e:
        print(f"❌ Keyword matching error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all dependency checks."""
    print("=" * 80)
    print("NLP Dependencies Check")
    print("=" * 80)
    print()

    all_ok = True

    # Check core packages
    print("--- Core Packages ---")
    all_ok &= check_package("pydantic")
    all_ok &= check_package("nltk")
    all_ok &= check_package("pymorphy3")
    all_ok &= check_package("pymorphy3-dicts-ru", "pymorphy3_dicts_ru")
    all_ok &= check_package("langdetect")
    all_ok &= check_package("regex")
    print()

    # Check NLTK data
    print("--- NLTK Data ---")
    check_nltk_data()  # Don't fail if data is missing - it will auto-download
    print()

    # Check pymorphy3
    print("--- pymorphy3 ---")
    all_ok &= check_pymorphy2()
    print()

    # Test functionality
    print("--- Functionality Tests ---")
    all_ok &= test_text_normalization()
    print()
    all_ok &= test_keyword_matching()
    print()

    # Summary
    print("=" * 80)
    if all_ok:
        print("✅ All checks passed! NLP functionality is ready to use.")
    else:
        print("❌ Some checks failed. Please install missing dependencies:")
        print()
        print("   pip install -r requirements.txt")
        print()
        print("For development dependencies:")
        print("   pip install -e '.[dev]'")
    print("=" * 80)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
