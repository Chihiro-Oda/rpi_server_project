# rpi_server_project/config.py

# --- 接続先の中央サーバー設定 ---
# IPアドレスではなくドメイン名を使用することで、SSL証明書エラーを回避し、
# Nginxのバーチャルホスト設定に正しくマッチさせます。
CENTRAL_SERVER_URL = "https://sotsusotsu.com"

# SSL証明書の検証を行うかどうか
# True (ブール値) または False (ブール値) を指定してください。文字列の "true" は不可です。
# 証明書の状態が不明な場合は一旦 False のままでも動作します。
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