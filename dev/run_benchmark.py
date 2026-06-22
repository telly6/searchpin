#!/usr/bin/env python3
"""
dev/run_benchmark.py — Run 3-scenario benchmark with 3-round iteration.
Domestic environment (no VPN/proxy). Results saved to dev/.
"""
import os, sys, json, time, re
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from search_engine import SearchEngine

# ── Scenarios ────────────────────────────────────────────────
SCENARIOS = {
    "场景1_PostgreSQL18": {
        "title": "PostgreSQL 18 数据库新版本",
        "rounds": [
            "PostgreSQL 18 release notes new features 2026",
            "postgresql.org docs release 18 AIO async I/O OAuth uuidv7 virtual generated columns",
            '"PostgreSQL 18" review benchmark AIO skip scan performance 2025',
        ]
    },
    "场景2_ClaudeOpus": {
        "title": "Claude Opus 5 / Fable 5 AI 模型发布",
        "rounds": [
            "Claude Opus 5 Anthropic latest model release 2026",
            "Anthropic Claude Opus 4.8 release SWE-bench benchmark coding performance 2026",
            "Claude Fable 5 Anthropic release model 2026",
        ]
    },
    "场景3_上海GPU": {
        "title": "上海 AI 算力 / 国产 GPU 芯片",
        "rounds": [
            "上海 AI算力中心 国产GPU芯片 2026年最新进展",
            "国产GPU 砺算科技 壁仞 摩尔线程 2026 上市 7G100 BR100",
            "上海智算中心 2026 GPU国产替代 昇腾 壁仞 沐曦 天数智芯 最新",
        ]
    },
}

def parse_timing_log(engine, query_prefix):
    """Parse timing log for this search to extract engine participation."""
    log_path = "/tmp/minisearch_timing.log"
    if not os.path.exists(log_path):
        return None
    with open(log_path) as f:
        lines = f.readlines()
    
    # Find the timing block for this query
    # Look backwards from end for pool entries
    pools = []
    for line in lines:
        m = re.match(r"\[TIMING\] pool=(\S+)\s+fetch=(\S+)s\s+parse=(\S+)s\s+results=(\d+)", line)
        if m:
            pools.append({
                "pool": m.group(1),
                "fetch": float(m.group(2)),
                "parse": float(m.group(3)),
                "results": int(m.group(4)),
            })
    
    # Get the last N pools (one set per search)
    return pools

def run_scenario(engine, scenario_name, scenario_info):
    """Run 3 rounds for one scenario."""
    print(f"\n{'='*60}")
    print(f"Starting: {scenario_name} — {scenario_info['title']}")
    print(f"{'='*60}")
    
    rounds_data = []
    total_engine_counts = {}
    all_timings = []
    
    for i, query in enumerate(scenario_info['rounds']):
        round_num = i + 1
        print(f"\n  --- Round {round_num}: {query[:60]}... ---")
        
        t0 = time.time()
        result = engine.search(query, max_results=10)
        t1 = time.time()
        
        if "error" in result and not result.get("results"):
            print(f"  ❌ Error: {result.get('error')}")
            rounds_data.append({
                "round": round_num,
                "query": query,
                "error": result.get('error'),
                "results": [],
                "timing": None,
            })
            continue
        
        timing = result.get("_timing", {})
        stages = timing.get("stages", {})
        results = result.get("results", [])
        pollution = result.get("_pollution")
        
        # Count engines
        engine_count = {}
        for r in results:
            eng = r.get("_engine", "unknown")
            engine_count[eng] = engine_count.get(eng, 0) + 1
            total_engine_counts[eng] = total_engine_counts.get(eng, 0) + 1
        
        merged = stages.get("num_results_merged", len(results))
        
        print(f"  Total: {timing.get('total', t1-t0):.2f}s | Search: {stages.get('search', 0):.2f}s | Rerank: {stages.get('rerank', 0):.2f}s | Merged: {merged}")
        print(f"  Engines: {engine_count}")
        if pollution and pollution.get("polluted"):
            print(f"  ⚠️ Pollution: {pollution.get('pollution_type', 'unknown')}")
        
        round_info = {
            "round": round_num,
            "query": query,
            "total_s": timing.get("total", round(t1 - t0, 2)),
            "search_s": stages.get("search", 0),
            "rerank_s": stages.get("rerank", 0),
            "merged": merged,
            "engines": engine_count,
            "results": [],
            "pollution": pollution,
        }
        
        all_timings.append({
            "total": timing.get("total", t1 - t0),
            "search": stages.get("search", 0),
            "rerank": stages.get("rerank", 0),
        })
        
        for j, r in enumerate(results):
            item = {
                "rank": j + 1,
                "rerank": r.get("_rerank_score", 0),
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "engine": r.get("_engine", ""),
                "snippet": r.get("snippet", "")[:200],
            }
            round_info["results"].append(item)
            print(f"    #{j+1} [{item['rerank']:.3f}] {item['engine']:12s} {item['title'][:70]}")
        
        rounds_data.append(round_info)
    
    return rounds_data, total_engine_counts, all_timings

def main():
    print("MiniSearch Benchmark — 国内环境 (Domestic, No VPN)")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: BAAI/bge-small-zh-v1.5")
    
    engine = SearchEngine(model_name="BAAI/bge-small-zh-v1.5")
    
    all_scenarios = {}
    global_engine_counts = {}
    
    for scenario_name, scenario_info in SCENARIOS.items():
        rounds_data, engine_counts, timings = run_scenario(engine, scenario_name, scenario_info)
        all_scenarios[scenario_name] = {
            "title": scenario_info["title"],
            "rounds": rounds_data,
            "total_engines": engine_counts,
            "avg_total": sum(t["total"] for t in timings) / len(timings) if timings else 0,
            "avg_search": sum(t["search"] for t in timings) / len(timings) if timings else 0,
            "avg_rerank": sum(t["rerank"] for t in timings) / len(timings) if timings else 0,
        }
        for eng, cnt in engine_counts.items():
            global_engine_counts[eng] = global_engine_counts.get(eng, 0) + cnt
    
    engine.close()
    
    # ── Generate Markdown Report ──────────────────────────────
    now = datetime.now()
    filename = f"dev/benchmark-domestic-{now.strftime('%Y%m%d')}.md"
    filepath = os.path.join(project_root, filename)
    
    lines = []
    lines.append(f"# MiniSearch 搜索引擎基准测试 — 国内直连环境")
    lines.append("")
    lines.append(f"> 测试时间: {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> 测试环境: macOS 宿主机直连（无 VPN / 无代理），国内网络")
    lines.append(f"> 搜索策略: 每场景 3 轮纵深搜索迭代")
    lines.append(f"> 嵌入模型: BAAI/bge-small-zh-v1.5")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 测试场景与查询")
    lines.append("")
    for sname, sinfo in SCENARIOS.items():
        lines.append(f"### {sinfo['title']}")
        for i, q in enumerate(sinfo['rounds']):
            lines.append(f"- R{i+1}: `{q}`")
        lines.append("")
    lines.append("---")
    lines.append("")
    
    for sname, sdata in all_scenarios.items():
        lines.append(f"## {sname}: {sdata['title']}")
        lines.append("")
        
        for rd in sdata['rounds']:
            lines.append(f"### 第 {rd['round']} 轮")
            lines.append(f"```")
            lines.append(f"Query: {rd['query']}")
            if rd.get('error'):
                lines.append(f"Error: {rd['error']}")
            else:
                lines.append(f"Total: {rd['total_s']}s | Search: {rd['search_s']}s | Rerank: {rd['rerank_s']}s | Merged: {rd['merged']}")
                eng_str = " + ".join(f"{k}({v})" for k, v in sorted(rd['engines'].items()))
                lines.append(f"Engines: {eng_str}")
            lines.append(f"```")
            lines.append("")
            
            if rd.get('pollution') and rd['pollution'].get('polluted'):
                lines.append(f"> ⚠️ 污染告警: {rd['pollution'].get('pollution_type', 'unknown')}")
                lines.append("")
            
            if rd.get('results'):
                lines.append("| # | Rerank | Title | URL | Engine |")
                lines.append("|---|--------|-------|-----|--------|")
                for r in rd['results']:
                    title_short = r['title'][:50].replace('|', '\\|')
                    url_short = r['url'][:60].replace('|', '\\|')
                    lines.append(f"| {r['rank']} | {r['rerank']:.3f} | {title_short} | {url_short} | {r['engine']} |")
                lines.append("")
        
        # Summary
        lines.append(f"**{sdata['title']} 汇总:**")
        lines.append("")
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 轮次 | 3 |")
        total_merged = sum(rd.get('merged', 0) for rd in sdata['rounds'])
        lines.append(f"| 累计合并 | ~{total_merged} 条 |")
        lines.append(f"| 平均总耗时 | {sdata['avg_total']:.2f}s |")
        lines.append(f"| 平均搜索 | {sdata['avg_search']:.2f}s |")
        lines.append(f"| 平均重排 | {sdata['avg_rerank']:.2f}s |")
        eng_str = " + ".join(f"{k}({v})" for k, v in sorted(sdata['total_engines'].items()))
        lines.append(f"| 引擎参与 | {eng_str} |")
        
        # Top1 avg
        all_top1 = []
        for rd in sdata['rounds']:
            if rd.get('results'):
                all_top1.append(rd['results'][0]['rerank'])
        if all_top1:
            lines.append(f"| 平均 Top1 rerank | {sum(all_top1)/len(all_top1):.3f} |")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # ── Engine Overview ───────────────────────────────────────
    lines.append("## 引擎参与总览")
    lines.append("")
    lines.append("```")
    max_cnt = max(global_engine_counts.values()) if global_engine_counts else 1
    for eng in sorted(global_engine_counts.keys()):
        cnt = global_engine_counts[eng]
        bar_len = max(1, int(cnt / max_cnt * 30))
        lines.append(f"  {eng:15s} {'█' * bar_len} {cnt} 条")
    lines.append("```")
    lines.append("")
    
    # ── Overall Summary ───────────────────────────────────────
    lines.append("## 整体总结")
    lines.append("")
    total_avg = sum(sdata['avg_total'] for sdata in all_scenarios.values()) / len(all_scenarios)
    lines.append(f"- 平均总耗时: ~{total_avg:.2f}s")
    lines.append(f"- 可用引擎: {len(global_engine_counts)} 个")
    lines.append(f"- 总引擎参与: {sum(global_engine_counts.values())} 条")
    lines.append("")
    
    # ── Environment ───────────────────────────────────────────
    lines.append("## 环境配置记录")
    lines.append("")
    lines.append("```")
    lines.append("测试环境: macOS 宿主机")
    lines.append("网络: 国内直连 (无 VPN / 无代理)")
    lines.append("搜索后端: Multi-engine (Sogou + Baidu + Bing CN + Bing Intl + Google + Yahoo + Yandex)")
    lines.append("策略: 每场景 3 轮纵深迭代")
    lines.append("嵌入模型: BAAI/bge-small-zh-v1.5")
    lines.append("```")
    
    report = "\n".join(lines)
    
    with open(filepath, "w") as f:
        f.write(report)
    
    print(f"\n{'='*60}")
    print(f"Report saved to: {filepath}")
    print(f"{'='*60}")
    
    # Also save JSON for completeness
    json_path = filepath.replace('.md', '.json')
    json_data = {
        "timestamp": now.isoformat(),
        "environment": "domestic (no VPN)",
        "scenarios": {},
    }
    for sname, sdata in all_scenarios.items():
        json_data["scenarios"][sname] = {
            "title": sdata["title"],
            "rounds": sdata["rounds"],
            "avg_total": sdata["avg_total"],
            "avg_search": sdata["avg_search"],
            "avg_rerank": sdata["avg_rerank"],
        }
    json_data["engine_totals"] = global_engine_counts
    with open(json_path, "w") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"JSON saved to: {json_path}")

if __name__ == "__main__":
    main()
