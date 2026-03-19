"""
Flow Metadata Extractor - 依存関係解決
解析済み FlowMetadata の依存先に対して追加 retrieve を行う
"""
import logging
from models import FlowMetadata
from retriever import MetadataRetriever

logger = logging.getLogger(__name__)


class DependencyResolver:
    """依存先の追加 retrieve を制御"""

    def __init__(self, retriever: MetadataRetriever):
        self.retriever = retriever

    def resolve(self, metadata: FlowMetadata) -> dict:
        """
        依存関係をもとに追加メタデータを retrieve する
        戻り値: { dep_type: { name: retrieved_path } }
        """
        results = {}

        for dep in metadata.dependencies:
            dep_key = f"{dep.dep_type}:{dep.name}"

            if dep.dep_type == "CustomObject":
                path = self.retriever.retrieve_custom_object(dep.name)
                results[dep_key] = {"retrieved": path is not None, "path": str(path) if path else None}

            elif dep.dep_type == "ApexClass":
                path = self.retriever.retrieve_apex_class(dep.name)
                results[dep_key] = {"retrieved": path is not None, "path": str(path) if path else None}

            elif dep.dep_type == "Flow":
                path = self.retriever.retrieve_flow(dep.name)
                results[dep_key] = {"retrieved": path is not None, "path": str(path) if path else None}

            else:
                logger.info(f"追加 retrieve 未対応のタイプ: {dep.dep_type} ({dep.name})")
                results[dep_key] = {"retrieved": False, "path": None, "reason": "unsupported_type"}

        logger.info(f"依存関係解決完了: {len(results)} 件処理")
        return results
