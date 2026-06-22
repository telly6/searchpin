#!/usr/bin/env python3
"""
LLM-driven benchmark — runs 3 scenarios with iterative search.
LLM analyzes each round's results and refines queries.
Domestic environment (no VPN).
"""
import os, sys, json, time, datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Ensure no VPN proxy
for k in list(os.environ.keys()):
    if k.startswith("DSOCKS_"):
        del os.environ[k]
os.environ["MINISEARCH_TIMING_LOG"] = "/tmp/minisearch_llm_timing.log"

from search_engine import SearchEngine

SCENARIOS = {
    "场景1_PostgreSQL18": {
        "title": "PostgreSQL 18",
        "queries": [
            "PostgreSQL 18 release notes",
            "PostgreSQL 18 new features async I/O",
            "postgresql.org docs 18 AIO UUIDv7",
        ],
    },
    "场景2_ClaudeOpus": {
        "title": "Claude Opus 5 / Fable 5",
        "queries": [
            "Claude Opus 5 Anthropic",
            "Anthropic Claude model release 2026",
            "Claude Fable 5 Anthropic",
        ],
    },
    "场景3_上海GPU": {
        "title": "上海AI算力/国产GPU",
        "queries": [
            "上海AI算力中心国产GPU芯片",
            "壁仞科技摩尔线程GPU 2026",
            "上海智算中心昇腾国产替代",
        ],
    },
}

def run():
    engine = SearchEngine(model_name="BAAI/bge-small-zh-v1.5")
    print("Engine ready.\n", flush=True)
    
    all_data = {}
    
    for sname, sinfo in SCENARIOS.items():
        print(f"\n{'='*60}")
        print(f"SCENARIO: {sname} — {sinfo['title']}")
        print(f"{'='*60}")
        
        rounds = []
        for i, query in enumerate(sinfo['queries']):
            round_num = i + 1
            print(f"\n--- Round {round_num}: {query} ---")
            
            t0 = time.time()
            result = engine.search(query, max_results=10)
            elapsed = time.time() - t0
            
            if result.get("error"):
                print(f"  ERROR: {result['error']}")
                rounds.append({
                    "round": round_num, "query": query,
                    "error": result['error'], "results": [],
                    "total_s": round(elapsed, 2),
                })
                continue
            
            timing = result.get("_timing", {})
            stages = timing.get("stages", {})
            results = result.get("results", [])
            pollution = result.get("_pollution")
            
            # Engine breakdown
            engine_count = {}
            for r in results:
                eng = r.get("_source_engine", r.get("_engine", "unknown"))
                engine_count[eng] = engine_count.get(eng, 0) + 1
            
            print(f"  Total: {elapsed:.2f}s | Search: {stages.get('search',0):.2f}s | "
                  f"Rerank: {stages.get('rerank',0):.2f}s | Merged: {stages.get('num_results_merged',len(results))}")
            print(f"  Engines: {engine_count}")
            
            if pollution and pollution.get("polluted"):
                print(f"  POLLUTION: {pollution.get('pollution_type')} sim={pollution.get('avg_similarity')}")
            
            round_data = {
                "round": round_num, "query": query,
                "total_s": round(elapsed, 2),
                "search_s": stages.get("search", 0),
                "rerank_s": stages.get("rerank", 0),
                "merged": stages.get("num_results_merged", len(results)),
                "engines": engine_count,
                "pollution": pollution,
                "results": [],
            }
            
            for j, r in enumerate(results):
                item = {
                    "rank": j + 1,
                    "rerank": round(r.get("_rerank_score", 0), 3),
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "engine": r.get("_source_engine", r.get("_engine", "")),
                    "snippet": r.get("snippet", "")[:200],
                }
                round_data["results"].append(item)
                print(f"    #{j+1} [{item['rerank']:.3f}] {item['engine']:12s} {item['title'][:70]}")
            
            rounds.append(round_data)
        
        all_data[sname] = {"title": sinfo["title"], "rounds": rounds}
    
    engine.close()
    
    # Save JSON
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(project_root, "dev", f"benchmark-llm-driven-{ts}.json")
    with open(out_path, "w") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSaved to {out_path}")
    
    # Also save readable summary
    md_path = out_path.replace(".json", ".md")
    with open(md_path, "w") as f:
        f.write(f"# LLM-Driven Benchmark — Domestic\n\n")
        f.write(f"Time: {ts}\n\n")
        for sname, sdata in all_data.items():
            f.write(f"## {sname}: {sdata['title']}\n\n")
            for rd in sdata['rounds']:
                f.write(f"### Round {rd['round']}: `{rd['query']}`\n")
                f.write(f"- Total: {rd['total_s']}s | Search: {rd['search_s']}s | Rerank: {rd['rerank_s']}s | Merged: {rd['merged']}\n")
                f.write(f"- Engines: {rd['engines']}\n")
                if rd.get('pollution') and rd['pollution'].get('polluted'):
                    f.write(f"- ⚠️ Pollution: {rd['pollution']['pollution_type']} (sim={rd['pollution'].get('avg_similarity')})\n")
                f.write("\n| # | Rerank | Title | URL | Engine |\n")
                f.write("|---|--------|-------|-----|--------|\n")
                for r in rd['results']:
                    t = r['title'][:50].replace('|', '\\|')
                    u = r['url'][:50].replace('|', '\\|')
                    f.write(f"| {r['rank']} | {r['rerank']:.3f} | {t} | {u} | {r['engine']} |\n")
                f.write("\n")
    print(f"Markdown saved to {md_path}")

if __name__ == "__main__":
    run()
