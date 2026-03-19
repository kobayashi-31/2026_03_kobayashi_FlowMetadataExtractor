"""
Flow Metadata Extractor - 認証関連
SOAP Login API を使って Salesforce に認証し、sf CLI にセッションを登録する
"""
import logging
import os
import subprocess
import urllib.request
import urllib.parse
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrgAuth:
    """Salesforce 認証情報"""
    instance_url: str
    access_token: str
    api_version: str


def load_env_file(env_path: str = ".env"):
    """
    簡単な .env パーサー (外部ライブラリ非依存)
    ファイルが存在すれば os.environ に読み込む
    """
    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()


def soap_login(
    username: str,
    password: str,
    security_token: str = "",
    login_url: str = "https://login.salesforce.com",
    api_version: str = "60.0",
) -> OrgAuth:
    """
    SOAP Login API で認証し、OrgAuth を返す。
    sf CLI やブラウザ不要。SSO 環境でもユーザー名+パスワードで認証可能。
    """
    soap_url = f"{login_url}/services/Soap/u/{api_version}"
    soap_body = (
        '<?xml version="1.0" encoding="utf-8" ?>'
        '<env:Envelope xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
        ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        ' xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">'
        "<env:Body>"
        '<n1:login xmlns:n1="urn:partner.soap.sforce.com">'
        f"<n1:username>{username}</n1:username>"
        f"<n1:password>{password}{security_token}</n1:password>"
        "</n1:login>"
        "</env:Body>"
        "</env:Envelope>"
    ).encode("utf-8")

    req = urllib.request.Request(
        soap_url,
        data=soap_body,
        headers={
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPAction": "login",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        resp_text = e.read().decode("utf-8")
        import re
        err_match = re.search(
            r"<sf:exceptionMessage>(.*?)</sf:exceptionMessage>",
            resp_text,
        )
        err_msg = err_match.group(1) if err_match else resp_text[:300]
        raise RuntimeError(f"SOAP Login failed: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"SOAP Login network error: {e}")

    # sessionId と serverUrl を抽出
    import re
    sid = re.search(r"<sessionId>(.*?)</sessionId>", resp_text)
    srv = re.search(r"<serverUrl>(.*?)</serverUrl>", resp_text)
    if not sid or not srv:
        raise RuntimeError("SOAP Login: failed to parse response")

    # serverUrl から instance URL を導出
    parsed = urllib.parse.urlparse(srv.group(1))
    instance_url = f"{parsed.scheme}://{parsed.netloc}"

    return OrgAuth(
        instance_url=instance_url,
        access_token=sid.group(1),
        api_version=api_version,
    )


def register_session_to_sf(auth: OrgAuth, alias: str = "soapOrg") -> bool:
    """
    取得した access_token を sf CLI に登録する
    sf org login access-token を使用
    """
    logger.info(f"sf CLI にセッションを登録中... (エイリアス: {alias})")

    # トークンの前後に不要な空白・改行があれば除去
    token_str = auth.access_token.strip()

    # デバッグ用にフォーマットを確認（生の値は出さない）
    is_valid_format = "!" in token_str
    logger.info(
        f"[DEBUG] トークン長: {len(token_str)}, !を含むか: {is_valid_format}"
    )
    if is_valid_format:
        parts = token_str.split("!", 1)
        logger.info(
            f"[DEBUG] OrgID部長: {len(parts[0])}, Token部長: {len(parts[1])}"
        )

    import shutil
    import os
    sf_cmd = shutil.which("sf")
    if not sf_cmd:
        logger.error("sf CLI が見つかりません。")
        return False

    cmd = [
        sf_cmd, "org", "login", "access-token",
        "--instance-url", auth.instance_url,
        "--alias", alias,
        "--no-prompt"
    ]

    env = os.environ.copy()
    env["SF_ACCESS_TOKEN"] = token_str

    try:
        # 環境変数経由で安全にトークンを渡す (Windows stdin バグ回避)
        result = subprocess.run(
            cmd,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=30
        )
        if result.returncode == 0:
            logger.info(f"sf CLI へのセッション登録成功: {alias}")
            return True
        else:
            logger.error(f"sf CLI へのセッション登録失敗: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"sf CLI ログインコマンド実行エラー: {e}")
        return False
