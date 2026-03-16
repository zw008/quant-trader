#!/bin/bash
# 安装 quant-trader skill 到 Claude Code 全局目录
# 安装后任意目录说"AH早报"即可触发

SKILL_DIR="$HOME/.claude/skills/quant-trader"
SKILL_SRC="$(dirname "$0")/skills/SKILL.md"

mkdir -p "$SKILL_DIR"
cp "$SKILL_SRC" "$SKILL_DIR/SKILL.md"

echo "✅ 安装完成：$SKILL_DIR/SKILL.md"
echo ""
echo "下一步："
echo "  1. mkdir -p reports && 编辑 reports/portfolio.md 填入你的持仓"
echo "  2. pip install yfinance pandas  （或 uv add yfinance pandas）"
echo "  3. 在 Claude Code 中说"AH早报"开始使用"
