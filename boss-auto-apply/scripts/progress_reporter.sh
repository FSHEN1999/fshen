#!/bin/bash
# 每 20min 扫 monitor 日志，汇总飞书
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# 找最新 monitor_2h_*.log
LOG=$(ls -t logs/monitor_2h_*.log 2>/dev/null | head -1)
if [ -z "$LOG" ]; then
  echo "no log found" >&2
  exit 1
fi

START=$(date +%s)
ROUND=0
INTERVAL=${INTERVAL:-1200}   # 默认 20min
MAX_MIN=${MAX_MIN:-120}       # 最多 2h

# 飞书推送函数 - 直接用 notify_feishu.py
feishu_push() {
  local msg="$1"
  cmd.exe /c "python -c \"from notify_feishu import notify; notify(r'''${msg}''')\"" 2>&1 | tail -3
}

while :; do
  ROUND=$((ROUND+1))
  NOW=$(date +%s)
  ELAPSED_MIN=$(( (NOW - START) / 60 ))

  # 关键指标统计
  APPLY_OK=$(grep -c "✅ 已沟通" "$LOG" 2>/dev/null || echo 0)
  AI_GREETING=$(grep -c "AI定制招呼" "$LOG" 2>/dev/null || echo 0)
  DOUBLE_SEND=$(grep -c "双发" "$LOG" 2>/dev/null || echo 0)
  AI_REPLY=$(grep -c "AI回复" "$LOG" 2>/dev/null || echo 0)
  RESUME_SENT=$(grep -c "附件简历" "$LOG" 2>/dev/null || echo 0)
  HR_REPLIES=$(grep -c "👔HR:" "$LOG" 2>/dev/null || echo 0)
  ERRORS=$(grep -cE "Traceback|ERROR|CRITICAL" "$LOG" 2>/dev/null || echo 0)
  ROUNDS_DONE=$(grep -c "轮次.*结束" "$LOG" 2>/dev/null || echo 0)
  LAST_ACTIVITY=$(tail -20 "$LOG" | grep -oE '^\S+ \S+' | tail -1 | head -c 19)

  MSG=$(cat <<EOF
📊 BOSS自动化 ${ELAPSED_MIN}min进度 [R${ROUND}]
━━━━━━━━━━━━━━
✅ 投递成功: ${APPLY_OK}
🎯 AI定制招呼: ${AI_GREETING}
📤 双发(模板+AI): ${DOUBLE_SEND}
💬 AI回复: ${AI_REPLY}
📎 简历已送: ${RESUME_SENT}
👔 HR回复条数: ${HR_REPLIES}
🔄 完成轮次: ${ROUNDS_DONE}
⚠ 错误: ${ERRORS}
⏱ 最后活动: ${LAST_ACTIVITY}
EOF
)
  echo "[$(date +%H:%M:%S)] push round $ROUND"
  feishu_push "$MSG"

  # 超时退出
  if [ $ELAPSED_MIN -ge $MAX_MIN ]; then
    echo "reached max $MAX_MIN min, exit"
    break
  fi
  sleep $INTERVAL
done
