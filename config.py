# rpi_server_project/config.py

# --- 接続先の中央サーバー設定 ---
# ポート8000ではなく、標準のHTTPSポート(443)を使用
# IPアドレス直打ちのため、SSL証明書エラーが出る可能性があります
CENTRAL_SERVER_URLS = [
    "http://34.236.210.19:8000",  # 1. 新サーバー (優先)
    "https://sotsuken-sub.com/",     # 2. 新ドメイン (DNS浸透後用)
    "http://54.236.101.217:8000",  # 3. 旧サーバー (予備・移行期間用)
    "https://sotsusotsu.com",
]

# SSL証明書の検証を行うかどうか
# IPアドレスでアクセスする場合や自己署名証明書の場合は False に設定
VERIFY_SSL = False

# APIのベースパス
API_BASE_PATH = "/api/"

# APIキー（将来のセキュリティ拡張用。今はダミー）
API_KEY = "dummy-secret-key-for-rpi-01"


# --- このデバイス（ラズベリーパイ）自体の設定 ---

# このデバイスがどの避難所に設置されているかを示すID
# このIDは、中央サーバーのShelterモデルのプライマリーキー(id)に対応させます。
# 運用前に、中央サーバーの管理画面で避難所を登録し、そのIDをここに設定します。
SHELTER_ID = "SHELTER_001"

# このデバイスを識別するための一意なID
# 複数台のラズパイを同じ避難所で使う場合などを想定し、ユニークな名前を付けます。
DEVICE_ID = "RPi_Shelter_A_01"


# --- アプリケーションの動作設定 ---

# QRコードを連続でスキャンする際のクールダウンタイム（秒）
QR_SCAN_COOLDOWN_SECONDS = 5