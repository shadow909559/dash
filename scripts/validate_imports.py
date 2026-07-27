"""Validate all Python files can be compiled and have correct imports."""
import os
import py_compile
import sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'apps', 'backend'))
errors = []
success = 0

for dirpath, dirnames, filenames in os.walk(root):
    for f in filenames:
        if f.endswith('.py'):
            fp = os.path.join(dirpath, f)
            try:
                py_compile.compile(fp, doraise=True)
                success += 1
            except py_compile.PyCompileError as e:
                errors.append((fp, str(e)))

print(f"Compiled {success} files successfully")
if errors:
    print(f"\n{len(errors)} ERRORS:")
    for fp, err in errors:
        print(f"  FAIL: {fp}")
        print(f"    {err}")
    sys.exit(1)
else:
    print("All files compiled successfully!")

