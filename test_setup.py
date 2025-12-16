#!/usr/bin/env python3
"""
Test script to verify basic setup and configuration.

This script checks that:
1. All dependencies are installed
2. Configuration can be loaded
3. Logging is working correctly
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all core dependencies can be imported."""
    print("Testing imports...")
    
    try:
        import pydantic
        print("✓ pydantic")
    except ImportError as e:
        print(f"✗ pydantic: {e}")
        return False
    
    try:
        import pydantic_settings
        print("✓ pydantic_settings")
    except ImportError as e:
        print(f"✗ pydantic_settings: {e}")
        return False
    
    try:
        import sqlalchemy
        print("✓ sqlalchemy")
    except ImportError as e:
        print(f"✗ sqlalchemy: {e}")
        return False
    
    print()
    return True


def test_configuration():
    """Test that configuration can be loaded."""
    print("Testing configuration...")
    
    try:
        from app.config.settings import Settings, get_settings
        
        # Try to load settings (will use defaults if .env doesn't exist)
        settings = get_settings()
        
        print(f"✓ Configuration loaded")
        print(f"  - Environment: {settings.app.environment}")
        print(f"  - Debug: {settings.app.debug}")
        print(f"  - Log level: {settings.logging.level}")
        print(f"  - Database host: {settings.database.host}")
        print()
        return True
        
    except Exception as e:
        print(f"✗ Configuration failed: {e}")
        print()
        return False


def test_logging():
    """Test that logging is working."""
    print("Testing logging...")
    
    try:
        from app.infra.logging.config import get_logger, LogContext
        
        logger = get_logger(__name__)
        
        # Test basic logging
        logger.info("Test log message")
        print("✓ Basic logging works")
        
        # Test context logging
        with LogContext(user_id=123, message_id=456):
            logger.info("Test log with context")
        print("✓ Context logging works")
        
        print()
        return True
        
    except Exception as e:
        print(f"✗ Logging failed: {e}")
        print()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("News Aggregator - Setup Verification")
    print("=" * 60)
    print()
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_configuration()))
    results.append(("Logging", test_logging()))
    
    # Print summary
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 All tests passed! Setup is complete.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print()
        print("Note: If you see errors about missing BOT_TOKEN or USERBOT_API_ID,")
        print("this is expected if you haven't created a .env file yet.")
        print("Copy .env.example to .env and fill in your credentials.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
