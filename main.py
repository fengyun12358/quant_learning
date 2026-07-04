"""
main.py — 量化研究调度入口
===========================
用法:
  python main.py                    # 打印菜单
  python main.py --exp 1            # 跑模拟数据冒烟测试
  python main.py --exp all          # 全部跑一遍, 结果写入 research/run_results.txt
"""
import sys, os, subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RESEARCH_DIR = os.path.join(PROJECT_ROOT, "research")
OUTPUT_FILE = os.path.join(RESEARCH_DIR, "run_results.txt")

EXPERIMENTS = {
    "1": ("exp01_smoke_test",       "模拟数据冒烟测试 (MA/RSI/Sizer)"),
    "2": ("exp02_sizer_comparison",  "真实ETF仓位管理对比"),
    "3": ("exp03_portfolio",         "等权投资组合"),
    "4": ("exp04_rebalancing",       "再平衡方式对比 (无/月度/阈值)"),
    "5": ("exp05_backtrader_ma",       "backtrader_ma"),
    "6": ("exp06_qmt_verify",          "QMT适配器架构验证"),
}


def run_experiment(name):
    script = os.path.join(PROJECT_ROOT, "experiments", f"{name}.py")
    label = EXPERIMENTS.get(name, (name, ""))[1] if name in EXPERIMENTS else name
    print(f"\n{'='*60}\n  运行: {label}\n{'='*60}")

    result = subprocess.run(
        [sys.executable, script],
        capture_output=True, cwd=PROJECT_ROOT,
    )
    stdout_text = result.stdout.decode("gbk", errors="replace")
    print(stdout_text)
    if result.stderr:
        stderr_text = result.stderr.decode("gbk", errors="replace")
        if stderr_text.strip():
            print("[STDERR]", stderr_text[:500])
    return stdout_text


if __name__ == "__main__":
    # 解析 --exp=N 或 -e N
    target = None
    for i, a in enumerate(sys.argv):
        if a in ("--exp", "-e") and i + 1 < len(sys.argv):
            target = sys.argv[i + 1]
        elif a.startswith("--exp="):
            target = a.split("=")[1]

    if target is None:
        print(__doc__)
        print("可用实验:")
        for k, (name, desc) in EXPERIMENTS.items():
            print(f"  {k}: {name:30s} — {desc}")
        sys.exit(0)

    if target == "all":
        os.makedirs(RESEARCH_DIR, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8-sig") as f:
            for k in EXPERIMENTS:
                stdout = run_experiment(EXPERIMENTS[k][0])
                f.write(stdout)
                f.write("\n")
        print(f"\n结果已保存: {OUTPUT_FILE}")
    elif target in EXPERIMENTS:
        run_experiment(EXPERIMENTS[target][0])
    else:
        print(f"未知实验: {target}, 可用: {list(EXPERIMENTS.keys())}")
