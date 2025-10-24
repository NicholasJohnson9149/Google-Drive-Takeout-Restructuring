#!/usr/bin/env python3
"""
Comprehensive test runner for Google Drive Takeout Restructuring System
Runs all tests to ensure the system works correctly
"""
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            cwd=Path(__file__).parent
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ PASSED ({duration:.2f}s)")
            if result.stdout:
                print(f"Output:\n{result.stdout}")
        else:
            print(f"❌ FAILED ({duration:.2f}s)")
            print(f"Error output:\n{result.stderr}")
            if result.stdout:
                print(f"Standard output:\n{result.stdout}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run comprehensive test suite"""
    print("🚀 Starting Comprehensive Test Suite for Google Drive Takeout Restructuring")
    print("This will verify that all components work correctly")
    
    # Track test results
    results = {}
    
    # 1. Unit Tests - PathNormalizer
    results['path_normalizer'] = run_command(
        "python -m pytest tests/unit/test_path_normalizer.py -v",
        "Unit Tests - PathNormalizer"
    )
    
    # 2. Unit Tests - FileScanner
    results['file_scanner'] = run_command(
        "python -m pytest tests/unit/test_file_scanner.py -v",
        "Unit Tests - FileScanner"
    )
    
    # 3. Integration Tests - Rebuilder v2
    results['rebuilder_integration'] = run_command(
        "python -m pytest tests/integration/test_rebuilder_v2_integration.py -v",
        "Integration Tests - Rebuilder v2"
    )
    
    # 4. End-to-End Tests - Complete Flow
    results['e2e_complete'] = run_command(
        "python -m pytest tests/e2e/test_complete_restructuring.py -v",
        "End-to-End Tests - Complete Restructuring Flow"
    )
    
    # 5. Regression Tests - Edge Cases and Errors
    results['regression'] = run_command(
        "python -m pytest tests/regression/test_edge_cases_and_errors.py -v",
        "Regression Tests - Edge Cases and Error Conditions"
    )
    
    # 6. Run existing tests to ensure no regressions
    results['existing_unit'] = run_command(
        "python -m pytest tests/unit/ -v --tb=short",
        "Existing Unit Tests"
    )
    
    results['existing_integration'] = run_command(
        "python -m pytest tests/integration/ -v --tb=short",
        "Existing Integration Tests"
    )
    
    # 7. Test coverage report
    results['coverage'] = run_command(
        "python -m pytest tests/ --cov=app --cov-report=term-missing",
        "Test Coverage Analysis"
    )
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 TEST SUITE SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25} {status}")
    
    print(f"\nOverall: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The restructuring system is working correctly.")
        print("\nThe system has been thoroughly tested and verified to handle:")
        print("  ✓ All Takeout folder naming patterns (Takeout, Takeout-1, Takeout 2, etc.)")
        print("  ✓ Path transformations and structure preservation")
        print("  ✓ Metadata file detection and skipping")
        print("  ✓ Duplicate file handling (rename and skip strategies)")
        print("  ✓ Large file processing and verification")
        print("  ✓ Error recovery and resource management")
        print("  ✓ Edge cases and unusual file structures")
        print("  ✓ System resource monitoring")
        print("  ✓ Progress reporting and callback integration")
        
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - Please review the failures above")
        print("The restructuring system may not work correctly in all scenarios.")
        return 1


if __name__ == "__main__":
    sys.exit(main())