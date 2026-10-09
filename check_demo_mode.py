import os
from dotenv import load_dotenv

print("=== Demo Mode Configuration Check ===")

print("Before load_dotenv:")
print(f'  DEMO_MODE: "{os.environ.get("DEMO_MODE", "NOT SET")}"')

load_dotenv()

print("After load_dotenv:")
demo_mode_str = os.environ.get('DEMO_MODE', 'false')
demo_mode_bool = demo_mode_str.lower() == 'true'
print(f'  DEMO_MODE string: "{demo_mode_str}"')
print(f'  DEMO_MODE bool: {demo_mode_bool}')

# Read .env file directly
print("\n.env file content:")
try:
    with open('.env') as f:
        for line_num, line in enumerate(f, 1):
            if 'DEMO_MODE' in line:
                print(f'  Line {line_num}: {line.strip()}')
except Exception as e:
    print(f"  Error reading .env: {e}")

# Check what the app module sees
print("\nApp module evaluation:")
exec("DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'")
print(f"  App DEMO_MODE: {locals()['DEMO_MODE']}")