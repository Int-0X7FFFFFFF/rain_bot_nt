#!/bin/bash

# 检查 .env.prod 是否存在，如果不存在则创建
if [ ! -f /app/.env.prod ]; then
    echo "Creating .env.prod file..."

    cat <<EOL > /app/.env.prod
DRIVER=~fastapi+~websockets+~aiohttp
HOST=127.0.0.1
PORT=1234
COMMAND_START=["/"]
COMMAND_SEP=["."]
ONEBOT_ACCESS_TOKEN=hello
WOWS_API__APPLICATION_ID=["432324", "12341", "4323", "432423", "4234"]
DB_CONFIG__CONN="postgres://postgres:12315@127.0.0.1:5432/sadad"
EOL

    echo ".env.prod file has been created successfully."
else
    echo ".env.prod already exists."
fi

# 执行传递给容器的命令
exec "$@"
