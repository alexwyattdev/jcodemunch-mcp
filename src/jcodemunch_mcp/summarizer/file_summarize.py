"""Generate per-file heuristic summaries from symbol information."""

from ..parser.symbols import Symbol


def _heuristic_summary(file_path: str, symbols: list[Symbol]) -> str:
    """Generate summary from symbol information."""
    if not symbols:
        return ""

    classes = [s for s in symbols if s.kind == "class"]
    functions = [s for s in symbols if s.kind == "function"]
    constants = [s for s in symbols if s.kind == "constant"]
    types = [s for s in symbols if s.kind == "type"]

    parts = []
    if classes:
        # Deduplicate by a qualified key so distinct classes that share the
        # same short name (e.g., in different namespaces) are not merged.
        # For Swift extensions, normalize by stripping the "+extension:<line>"
        # suffix so that a base type and its extensions are grouped together
        # under a single summary line.
        seen_keys: set[str] = set()
        unique_classes: list[tuple[str, Symbol]] = []
        class_container_ids: dict[str, set[str]] = {}
        for cls in classes:
            class_key = cls.qualified_name if cls.qualified_name else cls.name
            if "+extension:" in class_key:
                class_key = class_key.split("+extension:", 1)[0]
            class_container_ids.setdefault(class_key, set()).add(cls.id)
            if class_key not in seen_keys:
                seen_keys.add(class_key)
                unique_classes.append((class_key, cls))
        for class_key, cls in unique_classes[:2]:
            container_ids = class_container_ids[class_key]
            method_count = sum(1 for s in symbols if s.kind == "method" and s.parent in container_ids)
            parts.append(f"Defines {cls.name} class ({method_count} methods)")
    if functions:
        if len(functions) <= 3:
            names = ", ".join(f.name for f in functions)
            parts.append(f"Contains {len(functions)} functions: {names}")
        else:
            names = ", ".join(f.name for f in functions[:3])
            parts.append(f"Contains {len(functions)} functions: {names}, ...")
    if types and not parts:
        names = ", ".join(t.name for t in types[:3])
        parts.append(f"Defines types: {names}")
    if constants and not parts:
        parts.append(f"Defines {len(constants)} constants")

    return ". ".join(parts) if parts else ""


def generate_file_summaries(
    file_symbols: dict[str, list[Symbol]],
) -> dict[str, str]:
    """Generate heuristic summaries for each file from symbol data.

    Args:
        file_symbols: Maps file path -> list of Symbol objects for that file

    Returns:
        Dict mapping file path -> summary string
    """
    summaries = {}

    for file_path, symbols in file_symbols.items():
        heuristic = _heuristic_summary(file_path, symbols)
        summaries[file_path] = heuristic

    return summaries
