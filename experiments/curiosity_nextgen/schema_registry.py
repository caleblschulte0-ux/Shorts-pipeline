"""Versioned schema validation and compatibility analysis prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class CompatibilityMode(str, Enum):
    NONE = "none"
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"


@dataclass(frozen=True)
class SchemaField:
    name: str
    field_type: str
    required: bool = True
    default_present: bool = False
    nullable: bool = False
    sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("field name must be nonempty")
        if self.field_type not in {"str", "int", "float", "bool", "dict", "list", "sha256", "any"}:
            raise ValueError(f"unsupported field type {self.field_type!r}")
        if self.required and self.nullable:
            raise ValueError("required fields may not be nullable")


@dataclass(frozen=True)
class SchemaDefinition:
    name: str
    version: int
    fields: tuple[SchemaField, ...]
    allow_unknown_fields: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("schema name must be nonempty")
        if self.version < 1:
            raise ValueError("schema version must be >= 1")
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("schema fields must be unique")

    @property
    def field_map(self) -> dict[str, SchemaField]:
        return {field.name: field for field in self.fields}


@dataclass(frozen=True)
class PayloadValidation:
    valid: bool
    missing_fields: tuple[str, ...]
    unknown_fields: tuple[str, ...]
    type_errors: tuple[str, ...]
    sensitive_fields_present: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    mode: CompatibilityMode
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def _matches_type(value: object, expected: str) -> bool:
    if expected == "any":
        return True
    if expected == "str":
        return isinstance(value, str)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "dict":
        return isinstance(value, Mapping)
    if expected == "list":
        return isinstance(value, list)
    if expected == "sha256":
        return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())
    return False


def validate_payload(schema: SchemaDefinition, payload: Mapping[str, object]) -> PayloadValidation:
    fields = schema.field_map
    missing = sorted(
        name for name, field in fields.items()
        if field.required and name not in payload and not field.default_present
    )
    unknown = sorted(name for name in payload if name not in fields)
    type_errors: list[str] = []
    sensitive: list[str] = []

    for name, value in payload.items():
        field = fields.get(name)
        if field is None:
            continue
        if value is None:
            if not field.nullable:
                type_errors.append(f"{name}:null_not_allowed")
            continue
        if not _matches_type(value, field.field_type):
            type_errors.append(f"{name}:expected_{field.field_type}")
        if field.sensitive:
            sensitive.append(name)

    if schema.allow_unknown_fields:
        unknown = []
    return PayloadValidation(
        valid=not missing and not unknown and not type_errors,
        missing_fields=tuple(missing),
        unknown_fields=tuple(unknown),
        type_errors=tuple(sorted(type_errors)),
        sensitive_fields_present=tuple(sorted(sensitive)),
    )


def compare_schemas(
    old: SchemaDefinition,
    new: SchemaDefinition,
    *,
    mode: CompatibilityMode,
) -> CompatibilityResult:
    if old.name != new.name:
        return CompatibilityResult(False, mode, ("schema_name_changed",), ())
    if new.version <= old.version:
        return CompatibilityResult(False, mode, ("version_must_increase",), ())

    old_fields = old.field_map
    new_fields = new.field_map
    blockers: list[str] = []
    warnings: list[str] = []

    backward = mode in {CompatibilityMode.BACKWARD, CompatibilityMode.FULL}
    forward = mode in {CompatibilityMode.FORWARD, CompatibilityMode.FULL}

    for name, old_field in old_fields.items():
        replacement = new_fields.get(name)
        if replacement is None:
            if backward and not new.allow_unknown_fields:
                blockers.append(f"removed_field_breaks_old_payload:{name}")
            else:
                warnings.append(f"field_removed:{name}")
            continue
        if replacement.field_type != old_field.field_type:
            blockers.append(f"field_type_changed:{name}:{old_field.field_type}->{replacement.field_type}")
        if old_field.nullable and not replacement.nullable:
            blockers.append(f"nullable_narrowed:{name}")
        if not old_field.required and replacement.required and not replacement.default_present:
            blockers.append(f"optional_became_required:{name}")
        if old_field.sensitive and not replacement.sensitive:
            warnings.append(f"sensitive_marker_removed:{name}")

    for name, new_field in new_fields.items():
        if name in old_fields:
            continue
        if backward and new_field.required and not new_field.default_present:
            blockers.append(f"new_required_field_without_default:{name}")
        if forward and not old.allow_unknown_fields:
            blockers.append(f"old_reader_rejects_new_field:{name}")
        elif not new_field.required:
            warnings.append(f"optional_field_added:{name}")

    return CompatibilityResult(
        compatible=not blockers,
        mode=mode,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )


class SchemaRegistry:
    def __init__(self, definitions: Iterable[SchemaDefinition] = ()) -> None:
        self._schemas: dict[tuple[str, int], SchemaDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: SchemaDefinition) -> None:
        key = (definition.name, definition.version)
        if key in self._schemas:
            raise ValueError(f"duplicate schema version {definition.name}@{definition.version}")
        self._schemas[key] = definition

    def get(self, name: str, version: int) -> SchemaDefinition:
        return self._schemas[(name, version)]

    def latest(self, name: str) -> SchemaDefinition:
        versions = [version for schema_name, version in self._schemas if schema_name == name]
        if not versions:
            raise KeyError(name)
        return self._schemas[(name, max(versions))]

    def versions(self, name: str) -> tuple[int, ...]:
        return tuple(sorted(version for schema_name, version in self._schemas if schema_name == name))
