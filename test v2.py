"""
Check Dash installation and test compatibility
"""

print("=" * 60)
print("DASH COMPATIBILITY CHECK")
print("=" * 60)

# Check versions
try:
    import dash
    print(f"✓ Dash version: {dash.__version__}")
except ImportError:
    print("✗ Dash not installed!")
    exit(1)

try:
    import dash_bootstrap_components as dbc
    print(f"✓ Dash Bootstrap Components: {dbc.__version__}")
except ImportError:
    print("✗ Dash Bootstrap Components not installed")
    print("  Install: pip install dash-bootstrap-components")

try:
    import plotly
    print(f"✓ Plotly version: {plotly.__version__}")
except ImportError:
    print("✗ Plotly not installed")

try:
    import pandas
    print(f"✓ Pandas version: {pandas.__version__}")
except ImportError:
    print("✗ Pandas not installed")

try:
    import openpyxl
    print(f"✓ openpyxl version: {openpyxl.__version__}")
except ImportError:
    print("✗ openpyxl not installed")
    print("  Install: pip install openpyxl")

print("\n" + "=" * 60)
print("TESTING BASIC DASH FUNCTIONALITY")
print("=" * 60)

# Test if Upload component exists
try:
    from dash import dcc
    upload = dcc.Upload(id='test-upload', children='Test')
    print("✓ dcc.Upload component available")
except Exception as e:
    print(f"✗ dcc.Upload component error: {e}")

# Test if Input/Output work
try:
    from dash import Input, Output
    print("✓ Input/Output imports work")
except Exception as e:
    print(f"✗ Input/Output error: {e}")

# Test callback decorator
try:
    from dash import callback
    print("✓ @callback decorator available (Dash 2.x)")
except ImportError:
    print("ℹ @callback not available (using Dash 1.x style)")

print("\n" + "=" * 60)
print("RECOMMENDATIONS")
print("=" * 60)

# Parse version
major_version = int(dash.__version__.split('.')[0])

if major_version >= 2:
    print("✓ Dash 2.x detected - Modern syntax")
    print("  - Use app.run() instead of app.run_server()")
    print("  - Use prevent_initial_call carefully or avoid it")
    print("  - Import from 'dash' instead of 'dash.dependencies'")
else:
    print("⚠ Dash 1.x detected - Consider upgrading")
    print("  pip install --upgrade dash")

print("\n" + "=" * 60)
print("NEXT STEPS")
print("=" * 60)
print("1. Run: python test_button_simple.py")
print("   Open: http://localhost:8052")
print("   Click the button - does counter increment?")
print("")
print("2. If button works: Dash installation is OK")
print("   If button doesn't work: Dash is broken, reinstall")
print("")
print("3. If Dash works but Horizon dashboard doesn't:")
print("   - Check browser console (F12)")
print("   - Look for JavaScript errors")
print("   - Try different browser")
print("=" * 60)
