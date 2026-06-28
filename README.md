# hs-like-cardgame

軽量なハースストーン風カードゲームのプロトタイプ（Python / FastAPI）。

## 構成
- server/app/game/core.py : ゲームコア（TurnManager, ActionQueue, Game）
- server/app/main.py : FastAPI + WebSocket の最小サーバ
- client/index.html : 簡易クライアント（WebSocket）
- tests/test_game_core.py : 基本テスト
- .github/workflows/ci.yml : pytest を回す CI

## ローカル実行
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r server/requirements.txt
pytest -q
uvicorn server.app.main:app --reload
