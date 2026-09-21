"""Cross-module phantom-call checker (#143).

Catches calls like ``module.func()`` where ``func`` does not exist on the
resolved module — the exact defect class behind the scheduler agent's
never-working ``queue.enqueue(...)`` (#141) and the voice/knowledge agents'
nonexistent ``transcribe_audio``/``embed_texts`` imports (#142). Those were
invisible to every existing gate: syntax-valid, importable, and caught only
by broad excepts that converted the AttributeError into fabricated success.

What it checks, statically:
  1. ``import X`` … ``X.f()``   — does ``f`` exist on module X?
  2. ``from X import Y`` … ``Y.f()`` — does ``f`` exist on Y's module?
  3. ``from X import f`` … ``f()``   — does ``f`` exist as an attribute of X?

Known limits (accepted, documented): it does NOT attempt attribute calls on
instances (``obj.method()``), monkeypatched attributes, ``__getattr__``
modules, or C extensions. It only ever flags a call when BOTH the binding
and the attribute resolution are statically provable — so its false-positive
rate stays near zero, which is what makes it CI-safe as a hard gate.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent  # apps/backend
PACKAGE_ROOT = BACKEND_ROOT / "dash_backend"
STDLIB_TOP_LEVEL = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


@dataclass
class Finding:
    file: Path
    line: int
    call_name: str
    resolved_from: str
    missing_attribute: str
    origin: str  # "import-binding" | "from-import"

    def render(self) -> str:
        try:
            where = self.file.relative_to(BACKEND_ROOT)
        except ValueError:
            where = self.file  # synthetic trees (tests) live outside the repo
        return (
            f"{where}:{self.line}: "
            f"call to non-existent '{self.missing_attribute}' on "
            f"'{self.resolved_from}' (via {self.origin})"
        )


@dataclass
class _FileImports:
    """Import-derived bindings for one file."""

    # binding name -> module name it refers to
    module_bindings: dict[str, str] = field(default_factory=dict)
    # binding name -> (module, symbol) it was imported from
    symbol_bindings: dict[str, tuple[str, str]] = field(default_factory=dict)


def _package_submodule_names(package_dir: Path) -> set[str]:
    """Submodule names of a package (``from pkg import submodule`` is legal
    even when ``__init__.py`` never re-exports it — Python binds imported
    submodules as package attributes at runtime)."""
    names: set[str] = set()
    if not package_dir.is_dir():
        return names
    for child in package_dir.iterdir():
        if child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            names.add(child.stem)
        elif child.is_dir() and (child / "__init__.py").is_file():
            names.add(child.name)
    return names


def _module_attr_names(module_path: Path) -> set[str] | None:
    """Names defined/exported by a module file (top-level defs/classes/assigns
    plus its own imports and ``__all__``). None if unreadable."""
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None

    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, ast.Tuple):
                    names.update(
                        t.id for t in target.elts if isinstance(t, ast.Name)
                    )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    names.add("*")  # unknown surface -> suppress findings
                else:
                    names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.If):
            # conditional re-exports (typing.TYPE_CHECKING etc.)
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    for alias in inner.names:
                        names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Try):
            # optional-dependency imports inside try/except
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Import, ast.ImportFrom)):
                    for alias in inner.names:
                        names.add(alias.asname or alias.name.split(".")[0])

    # __all__ overrides everything when present
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            try:
                exported = {
                    ast.literal_eval(elt)
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant)
                }
                exported |= _package_submodule_names(module_path.parent)
                return exported
            except ValueError:
                pass

    if module_path.name == "__init__.py":
        names |= _package_submodule_names(module_path.parent)
    return names


def _collect_imports(tree: ast.AST) -> _FileImports:
    imports = _FileImports()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                imports.module_bindings[bound] = alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue  # relative imports: cross-package, out of scope
            for alias in node.names:
                if alias.name == "*":
                    continue
                imports.symbol_bindings[alias.asname or alias.name] = (
                    node.module,
                    alias.name,
                )
    return imports


def _resolve_module(module_name: str) -> Path | None:
    """Resolve a dotted module name to a file inside this backend package."""
    parts = module_name.split(".")
    if parts[0] != PACKAGE_ROOT.name:
        return None
    base = PACKAGE_ROOT.joinpath(*parts[1:])
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def check_file(path: Path, root: ast.AST) -> list[Finding]:
    imports = _collect_imports(root)
    findings: list[Finding] = []
    module_cache: dict[str, set[str] | None] = {}

    def attrs_of(module_name: str) -> set[str] | None:
        if module_name not in module_cache:
            target = _resolve_module(module_name)
            module_cache[module_name] = (
                _module_attr_names(target) if target else None
            )
        return module_cache[module_name]

    for node in ast.walk(root):
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        # Case 3: bare-name call of a from-imported symbol —
        # ``from x import f`` … ``f()`` where f does not exist on x.
        if isinstance(func, ast.Name) and func.id in imports.symbol_bindings:
            module_name, symbol = imports.symbol_bindings[func.id]
            attrs = attrs_of(module_name)
            if attrs is not None and "*" not in attrs and symbol not in attrs:
                findings.append(
                    Finding(path, node.lineno, symbol,
                            f"{module_name}.{symbol}", symbol, "from-import")
                )
            continue

        if not isinstance(func, ast.Attribute):
            continue
        value = func.value
        if not isinstance(value, ast.Name):
            continue

        binding = value.id
        attr = func.attr

        # Case 1: binding is an imported module
        if binding in imports.module_bindings:
            full = imports.module_bindings[binding]
            attrs = attrs_of(full)
            if attrs is None or "*" in attrs:
                continue
            if attr not in attrs:
                findings.append(
                    Finding(path, node.lineno, attr, full, attr, "import-binding")
                )

        # Case 2/3: binding came from a from-import
        elif binding in imports.symbol_bindings:
            module_name, symbol = imports.symbol_bindings[binding]
            attrs = attrs_of(module_name)
            if attrs is None or "*" in attrs:
                continue
            if symbol not in attrs:
                # the from-import itself is broken (case 3); report the call
                # site so the developer sees where the phantom is invoked
                findings.append(
                    Finding(path, node.lineno, attr, f"{module_name}.{symbol}",
                            attr, "from-import")
                )
                continue
            # symbol exists on its module — resolve it to its own module and
            # check the attribute there (class 2)
            symbol_file = _resolve_module(f"{module_name}.{symbol}")
            if symbol_file is None:
                continue
            symbol_attrs = _module_attr_names(symbol_file)
            if symbol_attrs is None or "*" in symbol_attrs:
                continue
            if attr not in symbol_attrs:
                findings.append(
                    Finding(path, node.lineno, attr,
                            f"{module_name}.{symbol}", attr, "from-import")
                )

    return findings


def iter_backend_files() -> list[Path]:
    files: list[Path] = []
    for base in (PACKAGE_ROOT, BACKEND_ROOT / "scripts"):
        files.extend(sorted(base.rglob("*.py")))
    return [f for f in files if "__pycache__" not in f.parts]


def main() -> int:
    findings: list[Finding] = []
    for path in iter_backend_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError):
            continue
        findings.extend(check_file(path, tree))

    for f in findings:
        print(f"PHANTOM: {f.render()}")
    if findings:
        print(f"\n{len(findings)} phantom call(s) found.")
        return 1
    print("OK: no cross-module phantom calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
