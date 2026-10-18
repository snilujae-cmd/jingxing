"""三策略公平对比示例，可在未安装Streamlit的电脑上执行。"""
import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core.simulation import run_simulation


def main():
    p = argparse.ArgumentParser(description="景行智调：同一客流与车队下比较三种调度策略")
    p.add_argument('--a', type=int, default=10, help='A线模拟车辆数')
    p.add_argument('--b', type=int, default=6, help='B线模拟车辆数')
    p.add_argument('--capacity', type=int, default=36)
    p.add_argument('--rate', type=float, default=200, help='整个A+B场景的基础每小时客流')
    p.add_argument('--minutes', type=int, default=240)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--scenario', choices=['平峰', '上午高峰', '下午高峰'], default='上午高峰')
    p.add_argument('--speed', type=float, default=15.0)
    p.add_argument('--out', default='comparison_demo.csv')
    args = p.parse_args()
    if args.a < 0 or args.b < 0 or args.capacity <= 0:
        p.error('车辆数不能为负，容量必须为正')
    params = {
        'duration_min': args.minutes, 'arrival_rate': args.rate,
        'fleet': {'A': args.a, 'B': args.b},
        'vehicle_capacities': {'A': [args.capacity] * args.a, 'B': [args.capacity] * args.b},
        'scenario_type': args.scenario, 'peak_multiplier': 2.0,
        'fixed_interval': 17, 'queue_threshold': 20, 'speed_kmh': args.speed,
        'decision_interval_min': 5, 'prediction_horizon_min': 45, 'beam_width': 5,
        'dispatch_penalty': 15, 'fairness_weight': 0.35,
    }
    rows = []
    for strategy in ('fixed', 'dynamic', 'optimized'):
        r = run_simulation(params, strategy=strategy, seed=args.seed)
        rows.append({
            'strategy': strategy, 'fleet_A': args.a, 'fleet_B': args.b,
            'vehicle_capacity': args.capacity, 'seed': args.seed,
            'demand_signature': r['demand_signature'],
            'arrivals': r['total_arrivals'], 'boarded': r['served'],
            'remaining_queue': r['unserved'], 'service_rate': round(r['service_rate'], 5),
            'wait_observed_person_min': r['total_wait_person_min'],
            'wait_observed_avg_min': r['avg_observed_wait_all'],
            'p95_boarded_wait_min': round(r['p95_wait'], 3),
            'departures': r['total_departures'],
        })
    if len({x['demand_signature'] for x in rows}) != 1:
        raise RuntimeError('三组实验的客流不一致，禁止比较')
    out = pathlib.Path(args.out)
    with out.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('仿真实验已完成（非景区实际运营效果）：')
    for x in rows:
        print(x['strategy'], '已上车',x['boarded'],'期末排队',x['remaining_queue'],
              '已观察等待(人·分钟)',x['wait_observed_person_min'],'发车',x['departures'])
    print('结果文件：', out.resolve())


if __name__ == '__main__':
    main()
