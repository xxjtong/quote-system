#!/bin/bash
# 报价系统自动化测试脚本
# 用法: ./run_tests.sh [选项]
#
# 选项:
#   -q, --quick        简洁输出 (默认)
#   -v, --verbose      详细输出
#   -m MODULE          指定模块 (auth/products/quotes/admin/edge)
#   -k EXPR            匹配测试名
#   --html             生成 HTML 报告
#   --help             帮助信息

set -euo pipefail

VENV_PYTHON="/opt/quote-system/venv/bin/python"
TEST_DIR="/opt/quote-system/tests"
ARGS="-v --tb=short"

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quick)  ARGS="-v --tb=short" ;;
        -v|--verbose) ARGS="-vv --tb=long" ;;
        -m) shift; TEST_DIR="$TEST_DIR/test_$1.py" ;;
        -k) shift; ARGS="$ARGS -k $1" ;;
        --html)
            # 确保 pytest-html 已安装
            $VENV_PYTHON -m pip install -q pytest-html 2>/dev/null || true
            ARGS="$ARGS --html=${2:-report.html} --self-contained-html"
            shift
            ;;
        --help)
            head -12 "$0" | tail -11
            exit 0
            ;;
        *) echo "未知选项: $1"; exit 1 ;;
    esac
    shift
done

echo "════════════════════════════════════════════"
echo "  报价系统 API 自动化测试"
echo "  目标: ${QUOTE_TEST_URL:-http://127.0.0.1:5000}"
echo "════════════════════════════════════════════"
echo ""

cd /opt/quote-system
exec $VENV_PYTHON -m pytest "$TEST_DIR" $ARGS "$@"
