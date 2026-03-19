"""
Flow Metadata Extractor - メタデータ Retrieve
sf CLI を使って Salesforce からメタデータを取得する
"""
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataRetriever:
    """sf CLI を使ったメタデータ取得"""

    def __init__(self, target_org: str = "", output_dir: str = "./output"):
        self.target_org = target_org
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def check_sf_cli(self) -> bool:
        """sf CLI がインストールされているか確認"""
        import shutil
        sf_cmd = shutil.which("sf")
        if not sf_cmd:
            return False

        try:
            result = subprocess.run(
                [sf_cmd, "--version"],
                capture_output=True, text=True, encoding="utf-8", timeout=15
            )
            if result.returncode == 0:
                logger.info(f"sf CLI 検出: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            logger.error("sf CLI が見つかりません。インストールしてください。")
        except subprocess.TimeoutExpired:
            logger.error("sf CLI のバージョン確認がタイムアウトしました。")
        return False

    def retrieve_flow(self, flow_name: str) -> Path | None:
        """指定 Flow のメタデータを retrieve"""
        logger.info(f"Flow を retrieve 中: {flow_name}")
        return self._retrieve_metadata(f"Flow:{flow_name}")

    def retrieve_flow_definition(self, flow_name: str) -> Path | None:
        """FlowDefinition（アクティブバージョン情報）を retrieve"""
        logger.info(f"FlowDefinition を retrieve 中: {flow_name}")
        return self._retrieve_metadata(f"FlowDefinition:{flow_name}")

    def retrieve_apex_class(self, class_name: str) -> Path | None:
        """Apex Class を retrieve"""
        logger.info(f"ApexClass を retrieve 中: {class_name}")
        return self._retrieve_metadata(f"ApexClass:{class_name}")

    def retrieve_custom_object(self, object_name: str) -> Path | None:
        """CustomObject を retrieve"""
        logger.info(f"CustomObject を retrieve 中: {object_name}")
        return self._retrieve_metadata(f"CustomObject:{object_name}")

    def _retrieve_metadata(self, metadata_spec: str) -> Path | None:
        """
        sf CLI でメタデータを retrieve する共通処理
        retrieve 先は self.raw_dir に統一
        """
        import shutil
        sf_cmd = shutil.which("sf")
        if not sf_cmd:
            raise RuntimeError("sf CLI が見つかりません。")

        cmd = [
            sf_cmd,
            "project",
            "retrieve",
            "start",
            "--metadata", metadata_spec,
            "--target-metadata-dir", str(self.raw_dir)
        ]
        if self.target_org:
            cmd.extend(["--target-org", self.target_org])

        logger.debug(f"実行コマンド: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", timeout=120
            )
            if result.returncode == 0:
                logger.info(f"retrieve 成功: {metadata_spec}")
                logger.debug(f"stdout: {result.stdout}")
                return self.raw_dir
            else:
                logger.error(f"retrieve 失敗: {metadata_spec}")
                logger.error(f"stderr: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"retrieve タイムアウト: {metadata_spec}")
            return None
        except Exception as e:
            logger.error(f"retrieve 中にエラー: {e}")
            return None

    def find_flow_xml(self, flow_name: str) -> Path | None:
        """retrieve 済みの Flow XML ファイルを探す"""
        # sf CLI の出力構造に合わせて検索
        patterns = [
            self.raw_dir / "flows" / f"{flow_name}.flow-meta.xml",
            self.raw_dir / "unpackaged" / "flows" / f"{flow_name}.flow-meta.xml",
        ]
        # ディレクトリ内を再帰検索
        for xml_file in self.raw_dir.rglob(f"{flow_name}.flow-meta.xml"):
            logger.info(f"Flow XML 発見: {xml_file}")
            return xml_file
        for p in patterns:
            if p.exists():
                return p
        logger.warning(f"Flow XML が見つかりません: {flow_name}")
        return None

    def load_local_xml(self, xml_path: str) -> Path | None:
        """ローカルの XML ファイルを直接読み込む（テスト用）"""
        p = Path(xml_path)
        if p.exists():
            logger.info(f"ローカル XML 読み込み: {p}")
            return p
        logger.error(f"ファイルが見つかりません: {xml_path}")
        return None
