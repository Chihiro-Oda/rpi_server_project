import requests
import config

# 生きているURLをキャッシュしておく（毎回チェックすると遅いため）
_cached_active_url = None


def get_active_central_url():
    """
    config.CENTRAL_SERVER_URLS の中から、接続可能なURLを返す。
    接続可能なURLが見つからない場合は、リストの最初のURLを返す（エラー表示用）。
    """
    global _cached_active_url

    # 既にキャッシュがあり、それがまだ有効ならそれを返す（簡易的なキャッシュ）
    if _cached_active_url:
        return _cached_active_url

    # リストを順番に試す
    for url in config.CENTRAL_SERVER_URLS:
        # 末尾スラッシュ除去
        base_url = url.rstrip('/')
        try:
            # 軽いリクエスト（HEADやルートへのGET）を送って生存確認
            # timeout=2 程度でサクサク次へ行く
            requests.get(base_url, timeout=2)

            # 成功したらキャッシュして返す
            _cached_active_url = base_url
            return base_url
        except requests.RequestException:
            continue

    # 全滅の場合はリストの先頭を返しておく
    return config.CENTRAL_SERVER_URLS[0].rstrip('/')