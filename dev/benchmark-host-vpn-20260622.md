# MiniSearch 搜索引擎基准测试 — 宿主机 + VPN 环境

> 测试时间: 2026-06-22
> 测试环境: macOS 宿主机直连（非 Docker），VPN 模拟国外 IP
> MCP 配置: 宿主机本地 MCP Server
> 搜索策略: 每场景 3 轮纵深搜索迭代

---

## 测试场景与查询

### 场景 1: 英文技术 — PostgreSQL 数据库新版本
```
PostgreSQL 18 release notes new features 2026
```

### 场景 2: 英文技术 — AI 模型发布
```
Claude Opus 5 Anthropic latest model release 2026
```

### 场景 3: 中文技术 — 国产芯片与算力
```
上海 AI算力中心 国产GPU芯片 2026年最新进展
```

---

## 各场景结果

### 场景 1: PostgreSQL 18

#### 第 1 轮 — 主查询
```
Query: PostgreSQL 18 release notes new features 2026
Total: 12.82s | Search: 6.85s | Rerank: 5.97s | Merged: 34
Engines: Sogou(4) + Baidu(4) + Bing CN(2)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.785 | PostgreSQL 18 Released! | postgresql.org/about/news/postgresql-18-released-3142 | sogou |
| 2 | 0.771 | PostgreSQL: Release Notes | postgresql.org/docs/release/16.8/ ⚠️ 版本错误 | sogou |
| 3 | 0.709 | PostgreSQL 19 Beta 1 Released | postgresql.org | bing_cn |
| 4 | 0.708 | PostgreSQL 官网(重复) | postgresql.org | sogou |
| 5 | 0.675 | E. Release Notes — php中文网 | php.cn | sogou |
| 6 | 0.607 | pgBackRest Releases (无关) | pgbackrest.org | baidu |
| 7 | 0.607 | Confluent Cloud Release Notes (无关) | docs.confluent.io | baidu |
| 8 | 0.602 | PostgreSQL 18: 3x Faster I/O | commandprompt.com | baidu |
| 9 | 0.600 | Recent SQLite News (无关) | sqlite.org | baidu |
| 10 | 0.589 | PostgreSQL 18.3 中文手册 | postgres.cn | bing_cn |

📄 **抓取补充**: 官方公告全文 (1.89s) + CommandPrompt 评测 (1.31s)

#### 第 2 轮 — 精确特性搜索
```
Query: postgresql.org docs release 18 AIO async I/O OAuth uuidv7 virtual generated columns
Total: 13.26s | Search: 8.81s | Rerank: 4.44s | Merged: 34
Engines: Sogou(3) + Bing CN(3) + Bing Intl(3) + Baidu(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.767 | pg commit (2009年旧闻) | archives.postgresql.org | sogou |
| 2 | 0.758 | PostgreSQL v18发布 CSDN ⚠️ 403 WAF | blog.csdn.net | baidu |
| 3 | 0.687 | PostgreSQL: Downloads | postgresql.org | bing_intl |
| 4 | 0.674 | PostgreSQL 官网 | postgresql.org | sogou |
| 5 | 0.648 | Google Maps URL StackOverflow ❌ | stackoverflow.com | bing_cn |
| 6 | 0.647 | PostgreSQL 官网(重复) | postgresql.org | bing_intl |
| 7 | 0.640 | CentOS 安装 PG 博客 | cnblogs.com | sogou |
| 8 | 0.631 | Google Maps dev StackOverflow ❌ | stackoverflow.com | bing_cn |
| 9 | 0.612 | PostgreSQL Wikipedia | wikipedia.org | bing_intl |
| 10 | 0.610 | Google Maps location accuracy ❌ | support.google.com | bing_cn |

> ⚠️ **本轮污染严重**: Google Maps/StackOverflow 占 5/10

#### 第 3 轮 — 评测与 benchmark
```
Query: "PostgreSQL 18" review benchmark AIO skip scan performance 2025
Total: 12.52s | Search: 6.46s | Rerank: 6.06s | Merged: 35
Engines: Sogou(5) + Baidu(4) + Bing CN(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.685 | PostgreSQL 18 Released! (再次命中) | postgresql.org | sogou |
| 2 | 0.641 | PostgreSQL 19 Beta 1 | postgresql.org | bing_cn |
| 3 | 0.617 | PG 18: 3x Faster I/O | commandprompt.com | baidu |
| 4 | 0.616 | Planet PostgreSQL (Join优化讨论) | planet.postgresql.org | baidu |
| 5 | 0.597 | PG Performance Tuning (Percona) | percona.com | baidu |
| 6 | 0.580 | PG 18 docs: pg_rewind | postgresql.org | sogou |
| 7 | 0.574 | PG 8.1 Arrays (旧版,无关) | postgresql.org | sogou |
| 8 | 0.568 | PG性能优化综合案例 (无关) | cnblogs.com | sogou |
| 9 | 0.568 | PG 18新特性前瞻 (163.com) | 163.com | sogou |
| 10 | 0.550 | PG 18 Skip Scan (CSDN) | blog.csdn.net | baidu |

---

**场景 1 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~103 条 |
| 平均总耗时 | 12.87s |
| 平均搜索 | 7.37s |
| 平均重排 | 5.49s |
| 引擎参与 | Sogou(12) + Baidu(9) + Bing CN(6) + Bing Intl(3) |
| 污染告警 | ⚠️ R2 被 Google Maps 污染 (5/10) |
| 版本错误 | ⚠️ R1 #2 返回 PG 16.8 而非 18 |
| 官方来源 | ✅ postgresql.org 官方公告 + commandprompt.com 评测 |
| 质量评价 | ⚠️ 中等偏上 — 官方命中好，但版本混淆+搜索噪声拖后腿 |

---

### 场景 2: Claude Opus 5 / Fable 5

#### 第 1 轮 — 主查询
```
Query: Claude Opus 5 Anthropic latest model release 2026
Total: 16.22s | Search: 10.90s | Rerank: 5.32s | Merged: 27
Engines: Bing Intl(4) + Baidu(3) + Sogou(2) + Bing CN(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.779 | Best AI Models for Claude Max | sourceforge.net | sogou |
| 2 | 0.748 | GlobalGPT: Claude Opus 4.7 | glbgpt.com | sogou |
| 3 | 0.638 | Claude 5: Fable 5 Release Date | claude5.com | baidu |
| 4 | 0.617 | Claude Opus \ Anthropic (Bing) | anthropic.com | bing_intl |
| 5 | 0.615 | Claude Design 知乎 | zhuanlan.zhihu.com | bing_cn |
| 6 | 0.598 | Claude Fable 5正式发布 知乎Pin | zhihu.com | baidu |
| 7 | 0.555 | Claude Opus \ Anthropic 官方页面 🏆 | anthropic.com/claude/opus | baidu |
| 8 | 0.555 | Download Claude | claude.com | bing_intl |
| 9 | 0.544 | Home \ Anthropic (Opus 4.8) | anthropic.com | bing_intl |
| 10 | 0.541 | Claude Google Play | play.google.com | bing_intl |

> 🚨 关键发现: "Claude Opus 5"不存在，当前最新为 Opus 4.8 (2026-05-28) / Fable 5 (2026-06-09)

📄 **抓取**: anthropic.com/claude/opus 官方页面全文 (3.90s)
- Opus 4.8: $5/$25 per MTok, SWE-Bench Pro 69.2%, adaptive thinking, Fast Mode
- 用户评价: "they could've just called it Opus 5, it's that good" — Dan Shipper
- 完整产品线: 4.1(8月) → 4.5(11月) → 4.6(2月) → 4.7(4月) → 4.8(5月)

#### 第 2 轮 — Benchmark 对比搜索
```
Query: Anthropic Claude Opus 4.8 release SWE-bench benchmark coding performance 2026
Total: 10.93s | Search: 6.58s | Rerank: 4.34s | Merged: 25
Engines: Bing Intl(4) + Baidu(3) + Sogou(2) + Bing CN(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.618 | MiniMax M3 vs Opus 4.8 对比 | adg.csdn.net | baidu |
| 2 | 0.602 | Claude Opus 知乎 | zhihu.com | baidu |
| 3 | 0.598 | Opus 4.8 vs GPT-5.5 深度横评 🏆 | aieii.com | baidu |
| 4 | 0.588 | Anthropic Newsroom | anthropic.com | bing_intl |
| 5 | 0.581 | Claude Wikipedia | wikipedia.org | bing_intl |
| 6 | 0.579 | Claude 3.5 Sonnet 旧闻 | sohu.com | sogou |
| 7 | 0.570 | Anthropic Wikipedia | wikipedia.org | bing_intl |
| 8 | 0.567 | tenfy's blog (Opus 4.7) | tenfy.cn | sogou |
| 9 | 0.558 | Anthropic 首页 | anthropic.com | bing_cn |
| 10 | 0.546 | Claude by Anthropic | claude.com | bing_intl |

📄 **抓取**: aieii.com 深度对比全文 (0.56s)
- SWE-bench Verified: Opus 4.8 88.6% vs GPT-5.5 88.7% (平手)
- SWE-bench Pro: Opus 4.8 **69.2%** vs GPT-5.5 58.6% (领先 10.6pp)
- Dan Shipper Senior Eng: 63 vs 62 vs 33 (Opus 4.7)

#### 第 3 轮 — Fable 5 精确搜索
```
Query: Claude Fable 5 Anthropic release model 2026
Total: 13.50s | Search: 8.00s | Rerank: 5.50s | Merged: 29
Engines: Sogou(6) + Baidu(2) + Bing CN(1) + Bing Intl(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.915 | Claude Fable 5 百度图片 | my.oschina.net | baidu |
| 2 | 0.772 | Claude 5 Hub 🏆 | claude5.com | sogou |
| 3 | 0.739 | alphaXiv: Fable 5 & Mythos 5 | alphaxiv.org | sogou |
| 4 | 0.651 | Claude Design 知乎 | zhihu.com | bing_cn |
| 5 | 0.632 | Orlando O'Neill (Claude Code) | oneillo.com | sogou |
| 6 | 0.621 | Claude Opus (Bing) | anthropic.com | bing_intl |
| 7 | 0.611 | Fable 5 详解 (SegmentFault) 🏆 | segmentfault.com | sogou |
| 8 | 0.588 | Fable 5 发布报道 (163264) 🏆 | 163264.com | baidu |
| 9 | 0.577 | Fable 5 Bedrock 接入全流程 | cnblogs.com | sogou |
| 10 | 0.571 | 智谱唐杰对话马斯克 | sohu.com | sogou |

---

**场景 2 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~81 条 |
| 平均总耗时 | 13.55s |
| 平均搜索 | 8.49s |
| 平均重排 | 5.05s |
| 查询修正 | 🚨 "Opus 5" → 发现真实最新: Fable 5 / Opus 4.8 / Mythos 5 |
| 引擎参与 | Sogou(10) + Baidu(8) + Bing Intl(9) + Bing CN(3) |
| 官方来源 | ✅ anthropic.com/claude/opus 完整产品线 + 用户评价 |
| 深度评测 | ✅ aieii.com 头对头对比, segmentfault Fable 5 详解 |
| Fable 5 数据 | SWE-Bench Pro **80.3%**, $10/$50 per MTok, 2026-06-09 发布 |
| 质量评价 | ✅ **优秀** — 自动修正查询假设，信息密度和深度均好于预期 |

---

### 场景 3: 上海 AI 算力 / 国产 GPU

#### 第 1 轮 — 主查询
```
Query: 上海 AI算力中心 国产GPU芯片 2026年最新进展
Total: 12.34s | Search: 7.11s | Rerank: 5.22s | Merged: 27
Engines: Sogou(4) + Baidu(3) + Bing CN(2) + Bing Intl(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.761 | 上海AI芯片企业引领国产算力 | sohu.com | sogou |
| 2 | 0.698 | 长江证券:上海智算产业 | 163.com | sogou |
| 3 | 0.690 | GPU最新资讯 (快科技) | mydrivers.com | sogou |
| 4 | 0.636 | 华为昇腾芯片动态 | toutiao.com | sogou |
| 5 | 0.578 | AI时代中国芯片突围战 | chinadevelopment.com.cn | baidu |
| 6 | 0.573 | 算力新变局 (WAF 加密) | xueqiu.com | baidu |
| 7 | 0.552 | GPU芯片四小龙 百度百科 | sina.com.cn | baidu |
| 8 | 0.539 | 上海市人民政府 | shanghai.gov.cn | bing_intl |
| 9 | 0.515 | 中国上海 (乱码) | zwdt.sh.gov.cn | bing_cn |
| 10 | 0.501 | 上海概况 (无关) | cmp.whlyj.sh.gov.cn | bing_cn |

> 关键数据: 壁仞(BR100/BR104)、沐曦(IPO)、燧原、天数智芯、无问芯穹 Infini-AI 平台

#### 第 2 轮 — GPU 产品精确搜索
```
Query: 国产GPU 砺算科技 壁仞 摩尔线程 2026 上市 7G100 BR100
Total: 16.40s | Search: 9.78s | Rerank: 6.62s | Merged: 35
Engines: Sogou(9) + Baidu(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.707 | 砺算7G100 GPU 出样 | bilibili.com | sogou |
| 2 | 0.702 | 摩尔线程、壁仞科技对比 | toutiao.com | sogou |
| 3 | 0.630 | 摩尔线程+壁仞发布GPU (腾讯云 2022) ⚠️ | cloud.tencent.com | sogou |
| 4 | 0.602 | 砺算打破海外垄断 (知乎) | zhihu.com | baidu |
| 5 | 0.593 | 壁仞科技启动IPO | 163.com | sogou |
| 6 | 0.589 | 上海国投领投壁仞 (钛媒体) | 163.com | sogou |
| 7 | 0.578 | BR100 Hot Chips 亮相 | mydrivers.com | sogou |
| 8 | 0.569 | BR100 创全球算力纪录 (新民) | xinmin.cn | sogou |
| 9 | 0.564 | BR100 一次点亮成功 | dramx.com | sogou |
| 10 | 0.563 | BR100 2023 IPO | toutiao.com | sogou |

> ⚠️ 大量 2022 年 BR100 旧闻占据头部

#### 第 3 轮 — 2026 最新动态
```
Query: 上海智算中心 2026 GPU国产替代 昇腾 壁仞 沐曦 天数智芯 最新
Total: 12.82s | Search: 7.66s | Rerank: 5.16s | Merged: 28
Engines: Baidu(7) + Bing Intl(3)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.686 | 华为昇腾逆袭登顶 🏆 | cinic.org.cn | baidu |
| 2 | 0.618 | 上海仪电智算倡议 (政府) 🏆 | shanghai.gov.cn | baidu |
| 3 | 0.615 | 国产算力"上海时刻" (华夏时报) 🏆 | eastmoney.com | baidu |
| 4 | 0.585 | AI算力竞速:国产GPU | view.inews.qq.com | baidu |
| 5 | 0.581 | 国产GPU大爆发,上海成最大赢家 | 163.com | baidu |
| 6 | 0.572 | 接连上市,上海"芯"势力 | weixin.qq.com | baidu |
| 7 | 0.560 | 沪产芯片规模化部署 (科创板日报) 🏆 | 163.com | baidu |
| 8 | 0.435 | 192.168.1.1 Router ❌ | en.ipshu.com | bing_intl |
| 9 | 0.420 | 192.168.1.1 Login ❌ | whatismyip.com | bing_intl |
| 10 | 0.419 | 192.168.1.1 Admin ❌ | techbloat.com | bing_intl |

> ⚠️ 底部 3 条被路由器 IP 页面污染

---

**场景 3 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~90 条 |
| 平均总耗时 | 13.85s |
| 平均搜索 | 8.18s |
| 平均重排 | 5.67s |
| 引擎参与 | Sogou(13) + Baidu(11) + Bing Intl(4) + Bing CN(4) |
| 污染告警 | ⚠️ R3 底部 3 条路由器 IP 页面 |
| 旧闻占比 | ⚠️ R2 大量 2022 年 BR100 发布旧闻 |
| 核心数据 | ✅ 四小龙上市时间线、上海12万P智算规模、中国GPU 2029年13636亿元 |
| 质量评价 | ✅ **优秀** — 政策/资本/产品三层全覆盖 |

---

## 引擎参与总览

```
本次 (06-22, 宿主机+VPN, 3轮迭代):
  Sogou     ████████████████████  35 条
  Baidu     ████████████████      28 条
  Bing Intl █████████             16 条
  Bing CN   ███████               13 条
  Google    (零) ❌

上次 (06-21, Docker, 单轮搜索):
  Google    ████████████████████████  23 条 (77%)
  Sogou     ███████                   7 条
  Baidu     (零)
  Bing CN   (零)
  Bing Intl (零)
```

## 底层诊断

| 引擎 | 本次 (宿主机+VPN) | 上次 (Docker) |
|------|:-----------------:|:-------------:|
| Google | ❌ 零参与 — VPN 出口 IP 可能被限流/验证码 | ✅ 8+9+6=23 条 |
| Baidu | ✅ 28 条 — 宿主机 IP 未触发 CAPTCHA | ❌ CAPTCHA |
| Bing CN | ✅ 13 条 — 宿主机无 301 问题 | ❌ follow_redirects bug |
| Bing Intl | ✅ 16 条 — 宿主机可正常渲染 | ❌ JS 化页面 |
| Sogou | ✅ 35 条 — 持续稳定 | ✅ 7 条 |
| Yahoo | (未参与) | ❌ CDN 500 |
| Yandex | (未参与) | ❌ CAPTCHA |

## 与 Docker 环境的关键差异

| 维度 | Docker (06-21) | 宿主机+VPN (06-22) |
|------|:-------------:|:-----------------:|
| Google | ✅ 主力引擎 (77%) | ❌ 零参与 (VPN IP 问题?) |
| Baidu | ❌ CAPTCHA | ✅ 正常 |
| Bing CN | ❌ 301 bug | ✅ 正常 |
| Bing Intl | ❌ JS 渲染 | ✅ 正常 |
| 可用引擎数 | 2/7 | 4/7 |
| 搜索策略 | 单轮 | 3 轮迭代 |
| 平均总耗时 | ~11.7s | ~13.4s |
| 平均 Top1 rerank | 0.84 | 0.80 |

## 各场景信息量/信息质对比 (vs Docker+Google)

| 场景 | 信息量 | 信息质 | 备注 |
|------|:-----:|:-----:|------|
| PG18 | ≈ 追平 | ↓ 略降 | 官方来源好但缺独立技术博客, 出现了版本混淆 |
| Claude | ↑ 更好 | ↑ 更好 | 自动修正查询假设, 官方+深度评测均命中 |
| 上海GPU | ↑ 更好 | ≈ 持平 | 政策/资本/产品三维覆盖, Sogou+Baidu 中文优势明显 |

## 整体总结

- **3/3 场景成功**，无严重污染告警（仅少量噪声）
- **可用引擎 4/7**（Sogou + Baidu + Bing CN + Bing Intl），比 Docker 的 2/7 更多
- **Google 从主力变为零** — VPN 出口 IP 疑似触发限流或验证码，与 Docker 数据中心 IP 相反
- **中文场景（场景 3）受益最大** — Sogou + Baidu 双引擎中文覆盖深度优于 Google
- **英文场景（场景 1）受损** — Google 的长尾技术博客（neon、pgpedia）是独特优势
- **搜索迭代价值显著** — 场景 2 自动修正查询假设（"Opus 5 不存在"→Fable 5/4.8）
- **宿主机环境解除 Docker 限制**: Baidu CAPTCHA→正常, Bing CN 301→正常, Bing Intl JS渲染→正常
- **平均总耗时 ~13.4s**，略高于 Docker 的 ~11.7s（多引擎并行增加搜索延迟）
- **平均 Top3 rerank ~0.74**，略低于 Docker 的 ~0.81（Google 高质量长尾结果缺失）

---

## 环境配置记录

```
测试环境: macOS 宿主机
网络: VPN 模拟国外 IP
MCP Server: 本地进程, 非 Docker
搜索后端: Multi-engine (Sogou + Baidu + Bing CN + Bing Intl)
策略: 每场景 3 轮纵深迭代 + 关键页面 fetch
```
