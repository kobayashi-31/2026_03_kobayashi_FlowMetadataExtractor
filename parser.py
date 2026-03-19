"""
Flow Metadata Extractor - Flow XML パーサー
Flow XML を解析し、FlowMetadata 構造に変換する
"""
import re
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from models import (
    FlowMetadata, Decision, DecisionRule, RecordOperation,
    ApexAction, SubflowCall, Formula, ActionCall,
    FieldReference, Dependency, Unknown, Warning,
)

logger = logging.getLogger(__name__)

# Salesforce Metadata XML の namespace
SF_NS = "http://soap.sforce.com/2006/04/metadata"


def ns(tag: str) -> str:
    """namespace 付きタグ名を返す"""
    return f"{{{SF_NS}}}{tag}"


def find_text(element: ET.Element, tag: str, default: str = "") -> str:
    """子要素のテキストを取得（namespace 対応）"""
    child = element.find(ns(tag))
    if child is not None and child.text:
        return child.text.strip()
    return default


class FlowParser:
    """Flow XML を解析して FlowMetadata を生成する"""

    def __init__(self):
        self.metadata = FlowMetadata()
        self._target_object = ""  # トリガ対象オブジェクト（フィールド解決用）

    def parse(self, xml_path: str | Path) -> FlowMetadata:
        """Flow XML ファイルを解析"""
        xml_path = Path(xml_path)
        logger.info(f"Flow XML 解析開始: {xml_path}")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # namespace を自動検出
        self._detect_namespace(root)

        # 基本情報
        self.metadata.flow_api_name = xml_path.stem.replace(".flow-meta", "")
        self.metadata.flow_name = find_text(root, "label", self.metadata.flow_api_name)
        self.metadata.description = find_text(root, "description")
        self.metadata.process_type = find_text(root, "processType")
        self.metadata.api_version = find_text(root, "apiVersion")
        self.metadata.status = find_text(root, "status")

        # 各要素を解析
        self._parse_start(root)
        self._parse_decisions(root)
        self._parse_formulas(root)
        self._parse_record_creates(root)
        self._parse_record_updates(root)
        self._parse_record_deletes(root)
        self._parse_record_lookups(root)
        self._parse_action_calls(root)
        self._parse_subflows(root)
        self._parse_assignments(root)
        self._parse_loops(root)

        # 依存関係を集約
        self._collect_dependencies()

        # 実行フローを構築
        self._build_execution_flow(root)

        logger.info(f"Flow XML 解析完了: 依存先 {len(self.metadata.dependencies)} 件")
        return self.metadata

    def _detect_namespace(self, root: ET.Element):
        """ルート要素から namespace を自動検出"""
        global SF_NS
        tag = root.tag
        if tag.startswith("{"):
            SF_NS = tag[1:tag.index("}")]
            logger.debug(f"namespace 検出: {SF_NS}")

    # ─── 開始条件 ───

    def _parse_start(self, root: ET.Element):
        """<start> 要素を解析"""
        start = root.find(ns("start"))
        if start is None:
            return

        self.metadata.trigger_type = find_text(start, "triggerType")
        self.metadata.target_object = find_text(start, "object")
        self._target_object = self.metadata.target_object

        # recordTriggerType (Create, Update, CreateAndUpdate, Delete)
        record_trigger_type = find_text(start, "recordTriggerType")
        if record_trigger_type:
            self.metadata.trigger_type += f" ({record_trigger_type})"

        # フィルタ条件
        self.metadata.start_filter_logic = find_text(start, "filterLogic")
        for filt in start.findall(ns("filters")):
            self.metadata.start_conditions.append({
                "field": find_text(filt, "field"),
                "operator": find_text(filt, "operator"),
                "value": self._get_value(filt),
            })
            # フィールド参照を記録
            field_name = find_text(filt, "field")
            if field_name:
                self._add_field_ref(field_name, "start_condition")

        # scheduledPaths
        for sp in start.findall(ns("scheduledPaths")):
            self.metadata.start_conditions.append({
                "type": "scheduledPath",
                "name": find_text(sp, "name"),
                "label": find_text(sp, "label"),
                "offset_number": find_text(sp, "offsetNumber"),
                "offset_unit": find_text(sp, "offsetUnit"),
                "time_source": find_text(sp, "timeSource"),
                "connector": find_text(sp, "connector"),
            })

    # ─── 分岐 ───

    def _parse_decisions(self, root: ET.Element):
        """<decisions> 要素を解析"""
        for dec_elem in root.findall(ns("decisions")):
            decision = Decision(
                name=find_text(dec_elem, "name"),
                label=find_text(dec_elem, "label"),
            )
            # defaultConnector
            dc = dec_elem.find(ns("defaultConnector"))
            if dc is not None:
                decision.default_connector = find_text(dc, "targetReference")

            # rules
            for rule_elem in dec_elem.findall(ns("rules")):
                rule = DecisionRule(
                    name=find_text(rule_elem, "name"),
                    label=find_text(rule_elem, "label"),
                )
                # connector
                conn = rule_elem.find(ns("connector"))
                if conn is not None:
                    rule.connector = find_text(conn, "targetReference")

                # conditions
                for cond in rule_elem.findall(ns("conditions")):
                    rule.conditions.append({
                        "left": find_text(cond, "leftValueReference"),
                        "operator": find_text(cond, "operator"),
                        "right": self._get_value(cond, value_tag="rightValue"),
                    })
                    # フィールド参照を記録
                    left_ref = find_text(cond, "leftValueReference")
                    if left_ref:
                        self._add_field_ref(left_ref, "decision")

                decision.rules.append(rule)
            self.metadata.decisions.append(decision)

    # ─── 数式 ───

    def _parse_formulas(self, root: ET.Element):
        """<formulas> 要素を解析"""
        for f_elem in root.findall(ns("formulas")):
            expression = find_text(f_elem, "expression")
            formula = Formula(
                name=find_text(f_elem, "name"),
                data_type=find_text(f_elem, "dataType"),
                expression=expression,
                referenced_fields=self._extract_field_refs_from_expression(expression),
            )
            self.metadata.formulas.append(formula)

            # 数式内のフィールド参照を記録
            for field_name in formula.referenced_fields:
                self._add_field_ref(field_name, "formula")

    # ─── レコード操作 ───

    def _parse_record_creates(self, root: ET.Element):
        """<recordCreates> 要素を解析"""
        for elem in root.findall(ns("recordCreates")):
            op = self._parse_record_operation(elem, "create")
            self.metadata.record_creates.append(op)

    def _parse_record_updates(self, root: ET.Element):
        """<recordUpdates> 要素を解析"""
        for elem in root.findall(ns("recordUpdates")):
            op = self._parse_record_operation(elem, "update")
            self.metadata.record_updates.append(op)
            # 更新項目を記録
            for assignment in op.field_assignments:
                self._add_updated_field(
                    assignment.get("field", ""),
                    op.object_name
                )

    def _parse_record_deletes(self, root: ET.Element):
        """<recordDeletes> 要素を解析"""
        for elem in root.findall(ns("recordDeletes")):
            op = self._parse_record_operation(elem, "delete")
            self.metadata.record_deletes.append(op)

    def _parse_record_lookups(self, root: ET.Element):
        """<recordLookups> 要素を解析"""
        for elem in root.findall(ns("recordLookups")):
            op = self._parse_record_operation(elem, "lookup")
            self.metadata.record_lookups.append(op)

    def _parse_record_operation(self, elem: ET.Element, op_type: str) -> RecordOperation:
        """レコード操作要素の共通解析"""
        obj_name = find_text(elem, "object")
        # object が未指定の場合はトリガ対象を使う
        if not obj_name:
            obj_name = self._target_object

        op = RecordOperation(
            name=find_text(elem, "name"),
            label=find_text(elem, "label"),
            object_name=obj_name,
            operation_type=op_type,
        )

        # inputAssignments
        for ia in elem.findall(ns("inputAssignments")):
            op.field_assignments.append({
                "field": find_text(ia, "field"),
                "value": self._get_value(ia),
            })
            field_name = find_text(ia, "field")
            if field_name:
                self._add_field_ref(field_name, f"record_{op_type}", obj_name)

        # filters
        for filt in elem.findall(ns("filters")):
            op.filters.append({
                "field": find_text(filt, "field"),
                "operator": find_text(filt, "operator"),
                "value": self._get_value(filt),
            })

        # outputAssignments (lookupのみ)
        for oa in elem.findall(ns("outputAssignments")):
            field_name = find_text(oa, "field")
            if field_name:
                self._add_field_ref(field_name, "record_lookup", obj_name)

        return op

    # ─── アクション ───

    def _parse_action_calls(self, root: ET.Element):
        """<actionCalls> 要素を解析"""
        for elem in root.findall(ns("actionCalls")):
            action_type = find_text(elem, "actionType")
            action_name = find_text(elem, "actionName")
            name = find_text(elem, "name")
            label = find_text(elem, "label")

            inputs = []
            for ip in elem.findall(ns("inputParameters")):
                inputs.append({
                    "name": find_text(ip, "name"),
                    "value": self._get_value(ip),
                })

            outputs = []
            for op in elem.findall(ns("outputParameters")):
                outputs.append({
                    "name": find_text(op, "name"),
                    "assignToReference": find_text(op, "assignToReference"),
                })

            if action_type == "apex":
                self.metadata.apex_actions.append(ApexAction(
                    name=name, label=label,
                    apex_class=action_name,
                    inputs=inputs, outputs=outputs,
                ))
            else:
                self.metadata.action_calls.append(ActionCall(
                    name=name, label=label,
                    action_type=action_type,
                    action_name=action_name,
                    inputs=inputs, outputs=outputs,
                ))

    def _parse_subflows(self, root: ET.Element):
        """<subflows> 要素を解析"""
        for elem in root.findall(ns("subflows")):
            inputs = []
            for ia in elem.findall(ns("inputAssignments")):
                inputs.append({
                    "name": find_text(ia, "name"),
                    "value": self._get_value(ia),
                })
            outputs = []
            for oa in elem.findall(ns("outputAssignments")):
                outputs.append({
                    "name": find_text(oa, "name"),
                    "assignToReference": find_text(oa, "assignToReference"),
                })
            self.metadata.subflows.append(SubflowCall(
                name=find_text(elem, "name"),
                label=find_text(elem, "label"),
                flow_name=find_text(elem, "flowName"),
                inputs=inputs, outputs=outputs,
            ))

    # ─── 代入・ループ ───

    def _parse_assignments(self, root: ET.Element):
        """<assignments> 要素を解析"""
        for elem in root.findall(ns("assignments")):
            items = []
            for ai in elem.findall(ns("assignmentItems")):
                ref = find_text(ai, "assignToReference")
                items.append({
                    "assignTo": ref,
                    "operator": find_text(ai, "operator"),
                    "value": self._get_value(ai),
                })
                if ref:
                    self._add_field_ref(ref, "assignment")
            self.metadata.assignments.append({
                "name": find_text(elem, "name"),
                "label": find_text(elem, "label"),
                "items": items,
            })

    def _parse_loops(self, root: ET.Element):
        """<loops> 要素を解析"""
        for elem in root.findall(ns("loops")):
            self.metadata.loops.append({
                "name": find_text(elem, "name"),
                "label": find_text(elem, "label"),
                "collectionReference": find_text(elem, "collectionReference"),
                "iterationOrder": find_text(elem, "iterationOrder"),
            })

    # ─── 依存関係の集約 ───

    def _collect_dependencies(self):
        """解析した情報から依存関係リストを構築"""
        deps = self.metadata.dependencies
        seen = set()

        def _add(dep_type: str, name: str, context: str):
            key = (dep_type, name)
            if key not in seen and name:
                seen.add(key)
                deps.append(Dependency(dep_type=dep_type, name=name, context=context))

        # トリガ対象オブジェクト
        if self.metadata.target_object:
            _add("CustomObject", self.metadata.target_object, "trigger_object")

        # レコード操作のオブジェクト
        for op_list in [self.metadata.record_creates, self.metadata.record_updates,
                        self.metadata.record_deletes, self.metadata.record_lookups]:
            for op in op_list:
                if op.object_name:
                    _add("CustomObject", op.object_name, f"record_{op.operation_type}")

        # Apex クラス
        for apex in self.metadata.apex_actions:
            _add("ApexClass", apex.apex_class, "apex_action")
            # Apex 内部の依存は不明なので warning
            self.metadata.warnings.append(Warning(
                warning_type="apex_dependency",
                description=f"Apex クラス '{apex.apex_class}' の内部依存は Flow XML からは不明です",
                severity="medium",
            ))

        # サブフロー
        for sf in self.metadata.subflows:
            _add("Flow", sf.flow_name, "subflow")

        # アクション
        for ac in self.metadata.action_calls:
            _add(ac.action_type, ac.action_name, "action_call")

    # ─── ユーティリティ ───

    def _get_value(self, elem: ET.Element, value_tag: str = "value") -> str:
        """値要素を取得（stringValue / numberValue / elementReference 等に対応）"""
        val_elem = elem.find(ns(value_tag))
        if val_elem is None:
            return ""
        # 子要素から値を探す
        for child in val_elem:
            if child.text:
                tag_name = child.tag.replace(f"{{{SF_NS}}}", "")
                if tag_name == "elementReference":
                    return f"{{!{child.text.strip()}}}"
                return child.text.strip()
        if val_elem.text:
            return val_elem.text.strip()
        return ""

    def _add_field_ref(self, ref: str, context: str, object_name: str = ""):
        """フィールド参照を記録"""
        if not ref:
            return
        # $Record.Field__c → トリガ対象オブジェクトの Field__c
        obj = object_name or self._target_object
        field_name = ref

        if ref.startswith("$Record."):
            field_name = ref.replace("$Record.", "")
            obj = self._target_object
        elif ref.startswith("$Record__Prior."):
            field_name = ref.replace("$Record__Prior.", "")
            obj = self._target_object
        elif "." in ref and not ref.startswith("$"):
            # Object.Field 形式
            parts = ref.split(".", 1)
            obj = parts[0]
            field_name = parts[1] if len(parts) > 1 else ref

        self.metadata.referenced_fields.append(
            FieldReference(object_name=obj, field_name=field_name, context=context)
        )

    def _add_updated_field(self, field_name: str, object_name: str):
        """更新フィールドを記録"""
        if field_name:
            self.metadata.updated_fields.append(
                FieldReference(
                    object_name=object_name or self._target_object,
                    field_name=field_name,
                    context="record_update"
                )
            )

    def _extract_field_refs_from_expression(self, expression: str) -> list[str]:
        """数式文字列から {!xxx} 形式のフィールド参照を抽出"""
        if not expression:
            return []
        # {!$Record.Amount__c} や {!varName} のパターンを抽出
        refs = re.findall(r'\{!([^}]+)\}', expression)
        fields = []
        for ref in refs:
            if ref.startswith("$Record."):
                fields.append(ref.replace("$Record.", ""))
            elif ref.startswith("$Record__Prior."):
                fields.append(ref.replace("$Record__Prior.", ""))
            else:
                fields.append(ref)
        return fields

    def _build_execution_flow(self, root: ET.Element):
        """connector を辿って実行順序を構築"""
        # start の connector から開始
        start = root.find(ns("start"))
        if start is None:
            return

        start_connector = start.find(ns("connector"))
        if start_connector is None:
            return

        first_target = find_text(start_connector, "targetReference")
        self.metadata.execution_flow.append({
            "order": 1,
            "element": "start",
            "type": "start",
            "next": first_target,
        })

        # 全要素の connector マッピングを構築
        element_map = {}
        for tag in ["recordUpdates", "recordCreates", "recordDeletes",
                     "recordLookups", "actionCalls", "subflows", "assignments",
                     "loops", "screens"]:
            for elem in root.findall(ns(tag)):
                name = find_text(elem, "name")
                conn = elem.find(ns("connector"))
                next_ref = find_text(conn, "targetReference") if conn is not None else ""
                element_map[name] = {
                    "type": tag,
                    "label": find_text(elem, "label"),
                    "next": next_ref,
                }

        # decisions は特殊: connector が rules 内にある
        for elem in root.findall(ns("decisions")):
            name = find_text(elem, "name")
            # 全ルールの遷移先を収集
            branches = []
            first_rule_next = ""
            for rule_elem in elem.findall(ns("rules")):
                rule_conn = rule_elem.find(ns("connector"))
                if rule_conn is not None:
                    target = find_text(rule_conn, "targetReference")
                    branches.append(target)
                    if not first_rule_next:
                        first_rule_next = target
            # defaultConnector
            dc = elem.find(ns("defaultConnector"))
            default_next = find_text(dc, "targetReference") if dc is not None else ""
            if default_next:
                branches.append(default_next)

            element_map[name] = {
                "type": "decisions",
                "label": find_text(elem, "label"),
                "next": first_rule_next,  # メインパスは最初のルール
                "branches": branches,
                "default": default_next,
            }

        # 実行順に辿る（最大100要素、ループ防止）
        visited = set()
        current = first_target
        order = 2
        while current and current not in visited and order <= 100:
            visited.add(current)
            if current in element_map:
                info = element_map[current]
                self.metadata.execution_flow.append({
                    "order": order,
                    "element": current,
                    "type": info["type"],
                    "label": info["label"],
                    "next": info["next"],
                })
                current = info["next"]
                order += 1
            else:
                break
