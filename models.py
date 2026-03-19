"""
Flow Metadata Extractor - データモデル定義
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldReference:
    """フィールド参照"""
    object_name: str
    field_name: str
    context: str  # "start_condition", "decision", "record_update", "formula" 等


@dataclass
class RecordOperation:
    """レコード操作（作成/更新/削除/参照）"""
    name: str
    label: str
    object_name: str
    operation_type: str  # "create", "update", "delete", "lookup"
    field_assignments: list[dict] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)


@dataclass
class DecisionRule:
    """分岐条件ルール"""
    name: str
    label: str
    conditions: list[dict] = field(default_factory=list)
    connector: str = ""


@dataclass
class Decision:
    """分岐"""
    name: str
    label: str
    rules: list[DecisionRule] = field(default_factory=list)
    default_connector: str = ""


@dataclass
class ApexAction:
    """Apex 呼び出し"""
    name: str
    label: str
    apex_class: str
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)


@dataclass
class SubflowCall:
    """サブフロー呼び出し"""
    name: str
    label: str
    flow_name: str
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)


@dataclass
class Formula:
    """数式"""
    name: str
    data_type: str
    expression: str
    referenced_fields: list[str] = field(default_factory=list)


@dataclass
class ActionCall:
    """汎用アクション呼び出し"""
    name: str
    label: str
    action_type: str
    action_name: str
    inputs: list[dict] = field(default_factory=list)
    outputs: list[dict] = field(default_factory=list)


@dataclass
class Dependency:
    """依存関係"""
    dep_type: str  # "CustomObject", "CustomField", "ApexClass", "Flow" 等
    name: str
    context: str  # どこで参照されているか


@dataclass
class Unknown:
    """不明点"""
    element: str
    description: str
    suggestion: str = ""


@dataclass
class Warning:
    """警告"""
    warning_type: str
    description: str
    severity: str = "medium"  # "low", "medium", "high"


@dataclass
class FlowMetadata:
    """Flow 解析結果の全体構造"""
    # 基本情報
    flow_name: str = ""
    flow_api_name: str = ""
    description: str = ""
    process_type: str = ""
    api_version: str = ""
    status: str = ""

    # トリガ情報
    trigger_type: str = ""
    target_object: str = ""
    start_conditions: list[dict] = field(default_factory=list)
    start_filter_logic: str = ""

    # 要素
    decisions: list[Decision] = field(default_factory=list)
    formulas: list[Formula] = field(default_factory=list)
    record_creates: list[RecordOperation] = field(default_factory=list)
    record_updates: list[RecordOperation] = field(default_factory=list)
    record_deletes: list[RecordOperation] = field(default_factory=list)
    record_lookups: list[RecordOperation] = field(default_factory=list)
    apex_actions: list[ApexAction] = field(default_factory=list)
    subflows: list[SubflowCall] = field(default_factory=list)
    action_calls: list[ActionCall] = field(default_factory=list)
    assignments: list[dict] = field(default_factory=list)
    loops: list[dict] = field(default_factory=list)

    # 依存関係
    dependencies: list[Dependency] = field(default_factory=list)
    referenced_fields: list[FieldReference] = field(default_factory=list)
    updated_fields: list[FieldReference] = field(default_factory=list)

    # 実行フロー
    execution_flow: list[dict] = field(default_factory=list)

    # 不明点・警告
    unknowns: list[Unknown] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
