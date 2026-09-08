#!/bin/bash
# 每日自动出稿，保留真实退出码；并发启动不覆盖正在写入的日志。
set -u
cd "$(dirname "$0")" || exit 1
mkdir -p state archive || exit 1
exec 9>state/auto-runner.lock
if ! flock -n 9; then
  echo "已有自动出稿入口运行，本次跳过"
  exit 0
fi
D=$(TZ=Asia/Shanghai date +%Y-%m-%d)
python3 -B auto_pipeline.py > "archive/auto-${D}.txt" 2>&1
status=$?
cp "archive/auto-${D}.txt" latest-auto.txt || exit 1
exit "$status"
