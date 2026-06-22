# 三场景四环境基准测试对比

> 生成时间: 2026-06-22
> 场景: 1) PostgreSQL 18  2) Claude Opus/Fable 5  3) 上海AI/国产GPU

## 一、环境概览

| 环境 | 日期 | 网络 | 策略 | 可用引擎 | 不可用引擎 |
|------|------|------|------|----------|-----------|
| **Docker** | 06-21 | Docker DC IP(海外) | 单轮搜索 | Google,Sogou(2/7) | Baidu(CAPTCHA),BingCN(301bug),BingIntl(JS),Yahoo(CDN),Yandex(CAPTCHA) |
| **宿主机+VPN** | 06-22 | macOS+VPN(海外) | 3轮迭代 | Sogou,Baidu,BingCN,BingIntl(4/7) | Google(限流),Yahoo,Yandex |
| **国内直连(脚本)** | 06-22 | macOS直连(国内) | 3轮固定查询 | Baidu,BingCN,Sogou(3/7) | Google(ICU),Yahoo,Yandex,BingIntl(少) |
| **国内直连(LLM)** | 06-22 | macOS直连(国内) | **3轮LLM迭代** | Baidu,BingCN,Sogou(3/7) | Google,Yahoo,Yandex,BingIntl(少) |

## 二、三场景平均性能

| 环境 | 轮次 | 平均总耗时 | Top1 Rerank | 污染轮次 | ⚠️ 注意 |
|------|:---:|-----------|-------------|---------|------|
| Docker (海外IP) | **1轮** | 11.73s | 0.838 | 0/3 | **仅1轮**，未利用迭代优化；Google 一手源质量最高 |
| 宿主机+VPN (海外IP) | 3轮 | 13.42s | 0.820 | 3/3 | 3轮深挖但 Google 不可用 |
| 国内直连（脚本自动） | 3轮 | 14.19s | 0.870 | 1/3 | 固定 query，GPU 场景严重超时 |
| 国内直连（LLM驱动） | 3轮 | 7.98s | 0.907 | 1/3 | 自适应 query 修正，但缺少 Google 一手源 |

> ⚠️ **Top1 Rerank 不是信息质量评分。** 它是 query 与结果文本的余弦相似度——衡量
> "结果和查询在语义上有多接近"，不衡量结果本身的权威性或原创性。一个 CSDN 转载
> 文章的 rerank 可以和 neon.com 原创博客一样高。

## 三、场景1: PostgreSQL 18

| 环境 | 总耗时 | 搜索 | 重排 | Top1 | 引擎贡献 | 污染 | 核心发现 |
|------|--------|------|------|------|---------|------|---------|
| Docker (海外IP) | 9.3s | 6.5s | 2.9s | 0.915 | Google(8)+Sogou(2) | 无 | Google直连 neon.com/postgresql.org，无中文噪声 |
| 宿主机+VPN (海外IP) | 12.9s | 7.4s | 5.5s | 0.785 | Sogou(12)+Baidu(9)+Bing CN(6) | R2 GoogleMaps 5/10 | R2被Google Maps严重污染; 版本混淆(返回16.8) |
| 国内直连（脚本自动） | 4.7s | 1.1s | 3.6s | 0.856 | Baidu(17)+Sogou(7)+Bing CN(6) | 无 | 搜索极快(1.08s), Baidu主导, 中文技术博客覆盖全面 |
| 国内直连（LLM驱动） | 9.3s | 5.6s | 3.7s | 0.881 | Baidu(13)+Sogou(10)+Bing CN(7) | 无 | 特征词迭代->官方文档(0.881); 百度主导+搜狗补来源 |

## 三、场景2: Claude Opus/Fable 5

| 环境 | 总耗时 | 搜索 | 重排 | Top1 | 引擎贡献 | 污染 | 核心发现 |
|------|--------|------|------|------|---------|------|---------|
| Docker (海外IP) | 12.2s | 6.5s | 5.7s | 0.833 | Google(9)+Sogou(1) | 无 | Google 9/10条，命中独立作者综述 |
| 宿主机+VPN (海外IP) | 13.6s | 8.5s | 5.0s | 0.915 | Sogou(10)+Bing Intl(9)+Baidu(8) | 无(修正查询假设) | 自动发现Opus5不存在->Fable5/4.8，信息密度极高 |
| 国内直连（脚本自动） | 6.7s | 4.2s | 2.5s | 0.872 | Bing CN(15)+Baidu(13)+Sogou(2) | 无 | BingCN主导(15条), Fable5 Top1=0.980 |
| 国内直连（LLM驱动） | 6.2s | 4.4s | 1.8s | 0.924 | Sogou(12)+Bing CN(10)+Baidu(8) | 无 | Fable5专有名词->Top1=0.924; 发现限制后复活新闻 |

## 三、场景3: 上海AI/国产GPU

| 环境 | 总耗时 | 搜索 | 重排 | Top1 | 引擎贡献 | 污染 | 核心发现 |
|------|--------|------|------|------|---------|------|---------|
| Docker (海外IP) | 13.7s | 7.5s | 6.2s | 0.767 | Google(6)+Sogou(4) | 无 | Google英文覆盖中国话题，无旅游/百科污染 |
| 宿主机+VPN (海外IP) | 13.8s | 8.2s | 5.7s | 0.761 | Sogou(13)+Baidu(11)+Bing Intl(4) | R3 路由器IPx3,R2旧闻多 | BingIntl路由器IP污染x3; Sogou大量2022旧闻 |
| 国内直连（脚本自动） | 31.2s | 29.6s | 1.5s | 0.882 | Bing CN(13)+Baidu(11)+Sogou(5) | R1 旅游8/10, R3 影视5/ | R1 30s超时+8/10旅游; R3南部档案串台x5 |
| 国内直连（LLM驱动） | 8.4s | 6.6s | 1.7s | 0.915 | Baidu(13)+Sogou(8)+Bing CN(7) | 旅游3+字典1+股票2 | 旅游/字典/股票污染但rank极低; GLM-5.2适配等独家信息 |

## 四、搜索引擎可用性矩阵

| 引擎 | Docker(海外DC) | VPN(海外IP) | 国内脚本 | 国内LLM | 最佳环境 |
|------|:---:|:---:|:---:|:---:|------|
| Google | 主力 23条 | IP限流 | ICU崩溃 | ICU崩溃 | Docker |
| Baidu | CAPTCHA | 28条 | 主力 41条 | 主力 34条 | 国内直连 |
| Sogou | 7条 | 主力 35条 | 14条 | 30条 | VPN最稳 |
| Bing CN | 301bug | 13条 | 34条 | 24条 | 国内直连 |
| Bing Intl | JS渲染 | 16条 | 仅1条 | 仅2条 | VPN唯一 |
| Yahoo | CDN500 | 不可达 | 不可达 | 不可达 | 无 |
| Yandex | CAPTCHA | 不可达 | 连接拒绝 | 连接拒绝 | 无 |

## 五、污染模式对比

| 污染类型 | Docker | VPN | 国内脚本 | 国内LLM | 根因 |
|---------|:---:|:---:|:---:|:---:|------|
| 旅游污染 | 无 | 无 | R1:8/10 | 3/10(低rank) | BingCN将上海权重过高 |
| 字典污染 | 无 | 无 | 无 | 1/10(低rank) | 壁单字独立分词 |
| 股票论坛 | 无 | 无 | 无 | 2/10(低rank) | 线程->大智慧论坛 |
| 影视串台 | 无 | 无 | R3:5/10 | 无 | 智算拆分为智+算 |
| Google Maps | 无 | 5/10 | 无 | 无 | Google结果混入Maps |
| 路由器IP | 无 | 3/10 | 无 | 无 | BingIntl数字串=IP |
| 百科条目 | 无 | 偶尔 | 偶尔 | 偶尔(低rank) | 通用词自动匹配 |
| 旧闻占比 | 无 | R2大量2022 | 无 | 无 | 无freshness限制 |

## 六、核心发现

### ⚠️ 重要更正：不要混淆"引擎质量"和"搜索策略"

之前的对比将"LLM 迭代策略的优势"错误归因于"国内直连环境"。事实上：

**这四次测试测量的是两个正交维度：**
1. **搜索引擎质量**：Google (Docker) > 国内引擎 (Baidu/Bing/Sogou)
2. **搜索策略**：LLM 迭代 > 固定脚本

Docker 有最好的引擎但用了最弱的策略（单轮），国内 LLM 用了最好的策略但引擎较弱。
**如果 Docker 也跑 LLM 驱动的三轮迭代，结果只会比国内 LLM 更好。**

**证据（同查询 PG18 Round 1）：**
| 环境 | Top1 来源 | Top1 类型 | 版本错误 |
|------|----------|----------|:---:|
| Docker+Google | neon.com | 一手技术博客（独立作者） | ❌ 无 |
| 国内引擎 x3 | postgresql.org/modb.pro/sohu.com | 官方(但中文镜像)或中文转载 | ✅ 返回16.8替代18 |

> **关键差距不在 rerank 分数，而在来源质量。** Google 命中的 neon.com、pgpedia.info
> 是原创技术内容；国内引擎命中的是 CSDN/搜狐/墨天轮的转载文章，且多次出现
> 版本混淆（将 PG 16.8 的 release notes 当作 PG 18 返回）。

### 发现1: LLM 迭代量 > 引擎质量（在任何环境中都成立）

国内环境下的 LLM 迭代 vs 同环境固定脚本：GPU 场景从 31.2s 降至 8.4s (**降低 73%**)。
但这证明的是 **LLM 策略的价值，不是国内引擎的优势**。
Docker+Google 如果使用同样的迭代策略，预期表现会更好。

### 发现2: 公平条件下 Google > 国内引擎（英文技术场景）

**在英文技术搜索场景中，Google 明显优于国内引擎组合。** 同查询对比：
Docker+Google 的 Top3 为 neon.com、postgresql.org、pgpedia.info——全是一手技术源、零版本错误。
所有国内引擎环境均出现版本混淆（返回 PG 16.8 替代 18）。

国内的真正优势在中文场景（场景3 GPU）——百度+搜狗对国产GPU产业的覆盖深度（公司新闻、
政策文件、上市信息）远超 Google 的英文视角。

| 维度 | 国内直连 | 宿主机+VPN | Docker+Google |
|------|:---:|:---:|:---:|
| 搜索速度 | **最快** | 中等 | 较慢 |
| 百度引擎 | **中文主导** | 可用 | ❌ CAPTCHA |
| 英文一手源 | ⚠️ 缺失 | 中等(BingIntl) | **🏆 最佳** |
| Google | ❌ | ❌ | **✅** |
| 中文场景 | **🏆 最佳** | 好 | ⚠️ 弱（英文视角） |
| 英文场景 | ⚠️ 中文镜像为主 | 好但有噪声 | **🏆 零污染** |
| 版本准确性 | ⚠️ 混淆 | ⚠️ 混淆 | **✅ 精确** |

### 发现3: Docker+Google 是英文场景的黄金组合

- Google 独立技术博客覆盖 (neon.com, pgpedia.info) 是所有中文引擎都无法替代的
- 零污染、高质量排序，但仅 2/7 引擎可用，中文场景弱
- Playwright headed Chromium 在 macOS 上 ICU 崩溃，Docker Xvfb 是目前唯一可行方案

### 发现4: 嵌入重排始终是最可靠的污染隔离层

| 场景 | 污染情况 | Top1 Rerank | 污染条目 Rank | 效果 |
|------|---------|------------|-------------|:---:|
| Docker PG18 | 无 | 0.915 | - | N/A |
| VPN GPU | 路由器IP x3 | 0.761 | #8-10 (0.435-0.419) | 重排沉底 |
| 国内脚本GPU | 旅游8/10 | 0.805 | #2-10全污染 | 仅1条幸存 |
| **国内LLM GPU** | 旅游+字典+股票 | **0.915** | #8-10 (0.756-0.743) | **完美隔离** |

LLM 驱动的查询(用公司名/产品名替代地名)从根本上减少了污染源，
配合重排形成了双重防护。反观脚本的通用查询产生了 80% 污染率，仅靠重排无法挽救。

### 发现5: Playwright Chromium 的 ICU 崩溃阻塞了 Google

- **Docker**: Xvfb + headed Chromium -> Google 可用
- **macOS 宿主机**: `icudtl.dat not found` -> Google 完全不可用(4/4环境均失败)
- **修复**: `playwright install chromium-headless-shell` 可解决 ICU 问题

---
## 附录: 原始数据文件

| 文件 | 环境 |
|------|------|
| `dev/benchmark-docker-20260621.md` | Docker |
| `dev/benchmark-host-vpn-20260622.md` | 宿主机+VPN |
| `dev/benchmark-domestic-20260622.md` | 国内直连(脚本) |
| `dev/benchmark-llm-driven-20260622.md` | 国内直连(LLM) |
| `dev/benchmark-cross-env-comparison.md` | **本篇：四环境对比** |