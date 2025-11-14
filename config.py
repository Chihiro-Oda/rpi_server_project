# rpi_server_project/config.py

# --- 接続先の中央サーバー設定 ---
# このURLの末尾には / を付けないのが一般的
CENTRAL_SERVER_URL = "http://127.0.0.1:8000"  # 開発中はローカルPC、本番では実際のサーバーIPやドメインに変更

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