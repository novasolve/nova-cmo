"""
Smoke tests to prevent regression of critical functionality.
"""
import importlib
import os
import sys
from pathlib import Path


def test_run_web_imports():
    """Test that run_web.py can be imported without errors."""
    try:
        importlib.import_module("cmo_agent.scripts.run_web")
    except ImportError as e:
        raise AssertionError(f"Failed to import run_web.py: {e}")


def test_run_agent_imports():
    """Test that run_agent.py can be imported without errors."""
    try:
        importlib.import_module("cmo_agent.scripts.run_agent")
    except ImportError as e:
        raise AssertionError(f"Failed to import run_agent.py: {e}")


def test_beautiful_logging_imports():
    """Test that beautiful_logging.py can be imported without errors."""
    try:
        importlib.import_module("cmo_agent.obs.beautiful_logging")
    except ImportError as e:
        raise AssertionError(f"Failed to import beautiful_logging.py: {e}")


def test_tqdm_enabled_by_env():
    """Test that force_tqdm is enabled in the default configuration."""
    try:
        # Import the module that should have force_tqdm configured
        import cmo_agent.core.state as state
        
        # Check if force_tqdm is enabled in the default config
        config = getattr(state, "DEFAULT_CONFIG", {})
        logging_config = config.get("logging", {})
        force_tqdm = logging_config.get("force_tqdm", False)
        
        assert force_tqdm in (1, True, "1"), f"Expected force_tqdm to be enabled in logging config, got {force_tqdm}"
        
    except Exception as e:
        raise AssertionError(f"Failed to check force_tqdm configuration: {e}")


def test_critical_files_exist():
    """Test that critical files exist."""
    critical_files = [
        "cmo_agent/scripts/run_web.py",
        "cmo_agent/scripts/run_agent.py", 
        "dev.sh",
        "cmo_agent/obs/beautiful_logging.py",
        "cmo_agent/core/state.py",
        ".env.example"
    ]
    
    missing = []
    for file_path in critical_files:
        if not Path(file_path).exists():
            missing.append(file_path)
    
    if missing:
        raise AssertionError(f"Missing critical files: {missing}")


def test_monitoring_function_exists():
    """Test that the configure_metrics_from_config function exists and is importable."""
    try:
        from cmo_agent.core.monitoring import configure_metrics_from_config
        # Test that it's callable
        assert callable(configure_metrics_from_config), "configure_metrics_from_config should be callable"
    except ImportError as e:
        raise AssertionError(f"Failed to import configure_metrics_from_config: {e}")


def test_env_checker_exists():
    """Test that the environment checker tool exists and works."""
    env_checker_path = Path("tools/check_env.py")
    if not env_checker_path.exists():
        raise AssertionError("Environment checker tools/check_env.py not found")
    
    # Test that it's importable
    import sys
    sys.path.insert(0, str(Path("tools")))
    try:
        import check_env
        assert hasattr(check_env, "check_environment"), "check_environment function not found"
        assert callable(check_env.check_environment), "check_environment should be callable"
    except ImportError as e:
        raise AssertionError(f"Failed to import check_env module: {e}")
    finally:
        sys.path.pop(0)


if __name__ == "__main__":
    # Simple test runner
    test_functions = [
        test_run_web_imports,
        test_run_agent_imports, 
        test_beautiful_logging_imports,
        test_tqdm_enabled_by_env,
        test_critical_files_exist,
        test_monitoring_function_exists,
        test_env_checker_exists
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("All smoke tests passed!")
        sys.exit(0)
