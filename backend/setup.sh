#!/bin/bash
set -e

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
SAM3_DIR="/opt/sam3"

echo "=== [1/4] Setting up PostgreSQL ==="
apt-get install -y postgresql > /dev/null 2>&1
service postgresql start
su - postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres';\"" 2>/dev/null || true
su - postgres -c "createdb furniture_db" 2>/dev/null || true
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/furniture_db"

echo "=== [2/4] Installing Python dependencies ==="
pip install --no-cache-dir --ignore-installed blinker
pip install --no-cache-dir -r "$BACKEND_DIR/requirements.txt"
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu128

echo "=== [3/4] Installing SAM3 ==="
if [ ! -d "$SAM3_DIR" ]; then
    git clone https://github.com/facebookresearch/sam3.git "$SAM3_DIR"
fi
pip install --no-cache-dir --no-deps -e "$SAM3_DIR"

echo "=== [4/4] Setting environment ==="
export LAMA_PYTHON=$(which python3)
export SEGMENTATION_PROJECT_DIR="$BACKEND_DIR/segmentation_module"

if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo ""
    echo "⚠️  .env 파일이 없습니다. 아래 환경변수를 설정하세요:"
    echo "    OPENAI_API_KEY, HF_TOKEN"
    echo "    cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env 후 편집하거나 export로 직접 설정하세요."
    echo ""
fi

echo ""
echo "✅ Setup complete."
echo ""
echo "서버 실행:"
echo "  cd $BACKEND_DIR && uvicorn main:app --host 0.0.0.0 --port 8000"
