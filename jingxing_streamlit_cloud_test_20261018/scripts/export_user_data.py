"""离线统一导出OD/站点/车辆/乘客状态，供User端联调。"""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.simulation import run_simulation
from core.exporter import write_exports


def main():
    cli = argparse.ArgumentParser(description="景行智调：导出同一次仿真的User端联调CSV")
    cli.add_argument("--strategy", choices=["fixed", "dynamic", "optimized"], default="optimized")
    cli.add_argument("--a", type=int, default=5)
    cli.add_argument("--b", type=int, default=3)
    cli.add_argument("--rate", type=float, default=120)
    cli.add_argument("--minutes", type=int, default=120)
    cli.add_argument("--seed", type=int, default=42)
    cli.add_argument("--outdir", default="outputs/demo")
    args = cli.parse_args()
    result = run_simulation({"duration_min": args.minutes, "arrival_rate": args.rate,
                             "fleet": {"A": args.a, "B": args.b},
                             "scenario_type": "上午高峰", "speed_kmh": 15},
                            strategy=args.strategy, seed=args.seed)
    path = write_exports(result, args.outdir)
    print(f"已生成 {path.resolve()}，运行编号：{result['run_id']}")
    print(f"到达 {result['total_arrivals']} 人，已上车 {result['served']} 人，"
          f"未上车 {result['unserved']} 人，完成 {result['completed']} 人，发车 {result['total_departures']} 趟")

if __name__ == "__main__":
    main()
