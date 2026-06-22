# MiniSearch 三场景基准测试 — LLM驱动迭代搜索

> **测试时间**: 2026-06-22 17:30-17:38
> **测试环境**: macOS 宿主机，国内直连（无 VPN / 无代理）
> **搜索策略**: LLM 深度参与，每场景 3 轮纵深搜索迭代
> **嵌入模型**: BAAI/bge-small-zh-v1.5（fallback 加载）
> **可用引擎**: 百度、搜狗、Bing CN、Bing Intl（Yandex/Yahoo/Google 国内不可达）

---

## 总体性能概览

| 场景 | 轮次 | 平均耗时 | 平均搜索 | 平均重排 | 主要引擎 | 污染 |
|------|------|----------|----------|----------|----------|------|
| PostgreSQL 18 | 3 | 9.34s | 5.63s | 3.71s | baidu(13)+sogou(10)+bing(7) | 0/3 |
| Claude Opus/Fable 5 | 3 | 6.23s | 4.39s | 1.84s | sogou(12)+bing(10)+baidu(8) | 0/3 |
| 上海AI/国产GPU | 3 | 8.36s | 6.62s | 1.73s | baidu(13)+sogou(8)+bing(7) | 0/3 |

---
## 场景1：PostgreSQL 18 数据库新版本

### 第 1 轮：`PostgreSQL 18 release notes new features`

- ⏱ 总耗时: 12.36s | 搜索: 8.18s | 重排: 4.18s | 合并: 25 条
- 🔧 引擎: cn.bing.com(5) + www.baidu.com(2) + www.sogou.com(3)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.850 | PostgreSQL: Release Notes | https://www.postgresql.org/docs/release/18.0/ | www.sogou.com |
| 2 | 0.849 | PostgreSQL 18 最新版本发布了,看看都有啥? - 墨天轮 | https://www.modb.pro/db/1971243032825573376 | www.baidu.com |
| 3 | 0.815 | PostgreSQL 18新特性揭秘：4大突破你绝对不知道的改变！_用户_性... | https://www.sohu.com/a/865222711_121924584 | www.sogou.com |
| 4 | 0.802 | PostgreSQL 18新特性前瞻\|索引\|主键\|key\|优化器\|postgresql\|... | https://www.163.com/dy/article/JPGNQ7OP0511CU | www.sogou.com |
| 5 | 0.790 | 【2025最新】PostgreSQL的安装、配置与使用指南 - 知乎 | https://zhuanlan.zhihu.com/p/1908417758892369 | cn.bing.com |
| 6 | 0.779 | PostgreSQL：文档：18：PostgreSQL 18.0 文档 ... | https://postgres.ac.cn/docs/current/index.htm | cn.bing.com |
| 7 | 0.772 | PostgreSQL: 世界上最先进的开源数据库 - PostgreSQL 数据库 | https://postgresql.ac.cn/ | cn.bing.com |
| 8 | 0.758 | PostgreSQL_百度百科 | https://baike.baidu.com/item/PostgreSQL/53024 | cn.bing.com |
| 9 | 0.758 | PostgreSQL 18 深度实战:异步 I/O + Skip Scan 索引革命——从 3... | https://www.chenxutan.com/d/3838.html | www.baidu.com |
| 10 | 0.755 | Windows 安装 PostgreSQL18 超详细保姆级教程-CSDN博客 | https://blog.csdn.net/m0_58648890/article/det | cn.bing.com |

### 第 2 轮：`PostgreSQL 18 AIO async I/O UUIDv7 virtual generated columns`

- ⏱ 总耗时: 6.97s | 搜索: 4.34s | 重排: 2.63s | 合并: 22 条
- 🔧 引擎: cn.bing.com(1) + www.baidu.com(7) + www.sogou.com(2)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.811 | PostgreSQL 18发布!性能飙升3倍 支持UUIDv - 百度知道 | https://neon.com/blog/postgres-18-beta-is-out | www.baidu.com |
| 2 | 0.791 | PostgreSQL: PostgreSQL 18 Released! | https://www.postgresql.org/about/news/postgre | www.sogou.com |
| 3 | 0.765 | PostgreSQL 18 深度解析:当异步 I/O 把数据库性能推进「3 倍时代... | http://chenxutan.com/d/2026.html | www.baidu.com |
| 4 | 0.760 | PostgreSQL 18 已发布:一文读懂核心变化-腾讯云开发者社区-腾讯云 | https://cloud.tencent.com/developer/article/2 | www.baidu.com |
| 5 | 0.758 | ...发布,新增AIO uuidv7 OAuth等功能_postgresql 18 analyze only- | https://blog.csdn.net/chensuiyi/article/detai | www.baidu.com |
| 6 | 0.748 | PostgreSQL 18 Beta 1发布,有哪些功能亮点?-CSDN博客 | https://tonydong.blog.csdn.net/article/detail | www.baidu.com |
| 7 | 0.748 | PostgreSQL 18 Released: 3x Faster I/O Performance & Upg | https://www.commandprompt.com/blog/postgresql | www.baidu.com |
| 8 | 0.724 | PostgreSQL Source Code: Data Fields | https://doxygen.postgresql.org/functions_g.ht | www.baidu.com |
| 9 | 0.708 | PostgreSQL 教程 \| 菜鸟教程 | https://www.runoob.com/postgresql/postgresql- | cn.bing.com |
| 10 | 0.697 | 随笔档案「2025年4月8日」：CentOS 7系统上安装PostgreSQL的详细... | https://www.cnblogs.com/huamoai/p/archive/202 | www.sogou.com |

### 第 3 轮：`postgresql.org docs 18 release`

- ⏱ 总耗时: 8.69s | 搜索: 4.36s | 重排: 4.33s | 合并: 28 条
- 🔧 引擎: cn.bing.com(1) + www.baidu.com(4) + www.sogou.com(5)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.881 | PostgreSQL: PostgreSQL 18 Beta 1 Released! | https://www.linuxcompatible.org/story/postgre | www.baidu.com |
| 2 | 0.853 | PostgreSQL 18: release plans · Issue #224 · ossc-db/pg_ | http://postgresql.org/ | www.baidu.com |
| 3 | 0.846 | PostgreSQL: Documentation: 18: PostgreSQL 18.4 Document | http://www.postgresql.org/docs/current/static | www.sogou.com |
| 4 | 0.833 | PostgreSQL: PostgreSQL 18 Released! | https://www.postgresql.org/about/news/postgre | www.sogou.com |
| 5 | 0.821 | PostgreSQL 17.6, 16.10, 15.14, 14.19, 13.22, and 18 Bet | https://blog.csdn.net/chensuiyi/article/detai | www.baidu.com |
| 6 | 0.813 | PostgreSQL: PostgreSQL 17.4, 16.8, 15.12, 14.17, and 13 | https://www.postgresql.org/message-id/1740061 | www.sogou.com |
| 7 | 0.807 | PostgreSQL：文档：18：PostgreSQL 18.0 文档 ... | https://postgres.ac.cn/docs/current/index.htm | cn.bing.com |
| 8 | 0.791 | PostgreSQL 18新特性前瞻\|索引\|主键\|key\|优化器\|postgresql\|... | https://www.163.com/dy/article/JPGNQ7OP0511CU | www.sogou.com |
| 9 | 0.790 | PostgreSQL v18发布,新增AIO uuidv7 OAuth等功能_postgresql 18 an | https://news.sohu.com/a/940076355_121124365 | www.baidu.com |
| 10 | 0.787 | PostgreSQL: Documentation: 18: pg_upgrade | https://www.postgresql.org/docs/current/pgupg | www.sogou.com |

---
## 场景2：Claude Opus 5 / Fable 5 AI 模型发布

### 第 1 轮：`Claude Opus 5 Anthropic latest model`

- ⏱ 总耗时: 6.48s | 搜索: 4.35s | 重排: 2.12s | 合并: 19 条
- 🔧 引擎: cn.bing.com(2) + www.baidu.com(4) + www.sogou.com(4)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.963 | Claude Opus 5 Anthropic latest model的最新相关信息 | https://www.php.cn/faq/2630042.html | www.baidu.com |
| 2 | 0.858 | Claude Opus \ Anthropic | https://www.anthropic.com/claude/opus | www.baidu.com |
| 3 | 0.846 | Claude Opus 4.5 深度解构:当AI 学会了“拒绝道歉”与“痛恨列表” -... | https://www.cnblogs.com/swizard/p/19312404 | www.sogou.com |
| 4 | 0.815 | Best AI Models for Claude Max | https://sourceforge.net/software/ai-models/in | www.sogou.com |
| 5 | 0.812 | Home \ Anthropic | https://www.anthropic.com/ | cn.bing.com |
| 6 | 0.811 | 刚刚,Anthropic首个神话级Claude 5正式解禁! | https://cloud.tencent.com/developer/article/2 | www.baidu.com |
| 7 | 0.809 | Claude 中文版：Claude 4.5 国内使用指南～（支持 Claude ... | https://www.claudezh.com/claude/claude-chines | cn.bing.com |
| 8 | 0.808 | Claude Opus 4 Reviews in 2026 | https://sourceforge.net/software/product/Clau | www.sogou.com |
| 9 | 0.802 | 仅仅间隔11天,Anthropic发布新一代通用大模型Claude Fable 5 | https://zhuanlan.zhihu.com/p/2047968995517657 | www.baidu.com |
| 10 | 0.783 | ...use-demo/README.md at main · anthropics/claude-quick | https://github.com/anthropics/anthropic-quick | www.sogou.com |

### 第 2 轮：`Anthropic Claude Opus release benchmark 2026`

- ⏱ 总耗时: 5.96s | 搜索: 4.36s | 重排: 1.6s | 合并: 15 条
- 🔧 引擎: cn.bing.com(6) + www.sogou.com(4)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.802 | GitHub - anthropics/original_performance_takehome: Anth | https://github.com/anthropics/original_perfor | www.sogou.com |
| 2 | 0.778 | Claude（Anthropic发布的大型语言模型）_百度百科 | https://baike.baidu.com/item/Claude/62812102 | cn.bing.com |
| 3 | 0.775 | 一年狂揽73亿美元投资 Anthropic引燃大模型战火_Claude_Opus_... | https://www.sohu.com/a/762385916_114986 | www.sogou.com |
| 4 | 0.738 | ANTHROPIC进展追踪：超越GPT-4的表现 CLAUDE 3有多强？__新浪... | http://stock.finance.sina.com.cn/stock/go.php | www.sogou.com |
| 5 | 0.725 | 全球AI新王诞生，Anthropic估值冲爆1.2万亿，首次反超 ... | https://www.36kr.com/p/3799097984080899 | cn.bing.com |
| 6 | 0.721 | GitHub - anthropics/anthropic-sdk-python · GitHub | https://github.com/anthropics/anthropic-sdk-p | www.sogou.com |
| 7 | 0.719 | The AI for Problem Solvers \| Claude by Anthropic | https://claude.com/product/overview | cn.bing.com |
| 8 | 0.718 | Anthropic（美国人工智能股份有限公司）_百度百科 | https://baike.baidu.com/item/Anthropic/626395 | cn.bing.com |
| 9 | 0.712 | 每天了解一家大模型公司（国外篇）：Anthropic - 知乎 | https://zhuanlan.zhihu.com/p/13568558856 | cn.bing.com |
| 10 | 0.705 | 领先一个身位，Anthropic正式启动IPO进程 - 虎嗅网 | https://www.huxiu.com/article/4863841.html | cn.bing.com |

### 第 3 轮：`Claude Fable 5 Anthropic model`

- ⏱ 总耗时: 6.25s | 搜索: 4.46s | 重排: 1.79s | 合并: 17 条
- 🔧 引擎: cn.bing.com(2) + www.baidu.com(4) + www.sogou.com(4)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.924 | Claude Fable 5 发布,这是 Anthropic 最强的模型,你现在就能用... | https://blog.csdn.net/chen_si_shang_/article/ | www.baidu.com |
| 2 | 0.921 | Claude Fable 5登场,Anthropic把“危险的好东西”拿出来卖了 | https://blog.csdn.net/qq_36729037/article/det | www.baidu.com |
| 3 | 0.888 | Claude Fable 5深度解析:Anthropic旗舰模型的技术架构、自适应推理... | https://blog.csdn.net/nmdbbzcl/article/detail | www.sogou.com |
| 4 | 0.872 | Claude Fable 5 - 百度百科 | https://cloud.tencent.com/developer/article/2 | www.baidu.com |
| 5 | 0.842 | Anthropic 恰乌里称有信心“未来几天”重新开放 Mythos 及Fable 5 AI ... | https://finance.sina.com.cn/tech/digi/2026-06 | www.sogou.com |
| 6 | 0.806 | Fable 5“复活”疑云背后：AI狂飙突进,刹车何时能造好？_模型_公... | https://www.sohu.com/a/1039591645_362225 | www.sogou.com |
| 7 | 0.783 | Claude深夜炸场!放出史上最强「危险级」模型Fable 5,价格太逆天 | https://zhuanlan.zhihu.com/p/2047990880032892 | www.baidu.com |
| 8 | 0.779 | Claude5受限 国产大模型替代窗口打开- CFi.CN 中财网 | https://fund.cfi.cn/p20260622000339.html | www.sogou.com |
| 9 | 0.767 | Claude 中文版：Claude 4.5 国内使用指南～（支持 Claude ... | https://www.claudezh.com/claude/claude-chines | cn.bing.com |
| 10 | 0.734 | Claude（Anthropic发布的大型语言模型）_百度百科 | https://baike.baidu.com/item/Claude/62812102 | cn.bing.com |

---
## 场景3：上海 AI 算力 / 国产 GPU 芯片

### 第 1 轮：`上海AI算力中心国产GPU芯片2026`

- ⏱ 总耗时: 6.89s | 搜索: 4.35s | 重排: 2.54s | 合并: 18 条
- 🔧 引擎: cn.bing.com(3) + www.baidu.com(4) + www.sogou.com(3)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.915 | 2026年,国产GPU领军者将如何颠覆AI市场?_季宇_集成电路_技术 | https://www.sohu.com/a/828346302_122006510 | www.sogou.com |
| 2 | 0.888 | 上海AI芯片企业引领国产算力发展_科技_模型_DeepSeek | https://www.sohu.com/a/870738139_122001006 | www.sogou.com |
| 3 | 0.882 | 国产芯片迎来新突破 创全球算力纪录通用GPU芯片在上海发布_科技_... | https://it.sohu.com/a/575782298_362042 | www.sogou.com |
| 4 | 0.877 | GPU芯片四小龙(包含沐曦股份、天数智... - 百度百科 | https://zhuanlan.zhihu.com/p/2023345265361331 | www.baidu.com |
| 5 | 0.829 | 2026,国产AI芯片,跨越天堑:从“推理”走向“训练” | https://xueqiu.com/2815370195/394823987?_ugc_ | www.baidu.com |
| 6 | 0.783 | 算力新变局\|深度 | https://mail.cndca.org.cn/mjzy/xwzx/mtjj/2083 | www.baidu.com |
| 7 | 0.760 | 为什么国产 AI 芯片的“心脏”,跳动在上海? - 知乎 | https://www.jfdaily.com/sgh/detail?id=4005688 | www.baidu.com |
| 8 | 0.756 | 【2026上海景點】自由行必讀!TOP16上海經典/熱門/新景點推薦 | https://gowithmarkhazyl.com/must-visit-places | cn.bing.com |
| 9 | 0.755 | 【2026最新】上海景點Top15必去.宮廷宴.外灘.武康路.上海 ... | https://kuolife.com/china-shanghai-attraction | cn.bing.com |
| 10 | 0.743 | 上海市文化和旅游局，上海官方中国旅游网站，上海旅游网站 ... | https://www.meet-in-shanghai.net/cn/index.htm | cn.bing.com |

### 第 2 轮：`壁仞科技 摩尔线程 GPU 2026 最新`

- ⏱ 总耗时: 9.45s | 搜索: 8.18s | 重排: 1.27s | 合并: 27 条
- 🔧 引擎: cn.bing.com(1) + www.baidu.com(4) + www.bing.com(2) + www.sogou.com(3)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.943 | 摩尔线程亮相2026智源大会:软硬全栈创新,构筑国产GPU算力坚实底座 | https://xueqiu.com/9372064849/385899450 | www.baidu.com |
| 2 | 0.882 | GPU芯片(通用GPU芯片) - 百度百科 | http://m.bjnews.com.cn/detail/178149527812976 | www.baidu.com |
| 3 | 0.850 | 摩尔线程_摩尔线程最新动态_IT之家 | https://www.ithome.com/tags/%e6%91%a9%e5%b0%9 | www.sogou.com |
| 4 | 0.824 | 资本加持下的国产GPU四小龙:打破英伟达垄断的最后征程,尚有多长... | http://wap.seccw.com/index.php/Index/detail/i | www.baidu.com |
| 5 | 0.800 | 壁仞科技、摩尔线程均完成智谱GLM-5.2适配 | https://new.qq.com/rain/a/20260617A06G4W00 | www.sogou.com |
| 6 | 0.762 | 壁仞摩尔完成智谱GLM-5.2适配,国产GPU响应SOTA模型_推理_方案... | https://www.sohu.com/a/1037904563_122066678 | www.sogou.com |
| 7 | 0.757 | 2026国产AI芯片公司Top10出炉!摩尔线程居第二 | http://finance.ce.cn/stock/gsgdbd/202606/t202 | www.baidu.com |
| 8 | 0.736 | 大智慧tv版 理想股票技术论坛 | https://www.55188.com/tag-7369575.html | www.bing.com |
| 9 | 0.732 | 【技术分析】大智慧linux版：使用体验分享，真实感受，不 ... | https://www.55188.com/thread-38428291-1-1.htm | www.bing.com |
| 10 | 0.719 | 壁_壁字的拼音,意思,字典释义 - 《新华字典》 - 汉辞宝 | https://www.hancibao.com/zi/58c1 | cn.bing.com |

### 第 3 轮：`上海智算中心 昇腾 壁仞 沐曦 天数智芯`

- ⏱ 总耗时: 8.73s | 搜索: 7.33s | 重排: 1.39s | 合并: 29 条
- 🔧 引擎: cn.bing.com(3) + www.baidu.com(5) + www.sogou.com(2)

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.843 | 5万颗芯片撬动AI供应链!天数智芯为何让字节跳动动心? | http://www.xinhuanet.com/20260126/85a97601422 | www.baidu.com |
| 2 | 0.823 | 大模型浪潮下迎算力巨变 上海芯片企业争做AI“潮人” _ 东方财富网 | https://finance.eastmoney.com/a/2025031333451 | www.sogou.com |
| 3 | 0.799 | 上海市人民政府新闻办公室 | https://www.shio.gov.cn/TrueCMS/shxwbgs/ywts/ | www.baidu.com |
| 4 | 0.792 | 上海市文化和旅游局，上海中国官方旅游网站，上海旅游网站 ... | https://www.meet-in-shanghai.net/tc/ | cn.bing.com |
| 5 | 0.784 | 上海市文化和旅游局，上海官方中国旅游网站，上海旅游网站 ... | https://www.meet-in-shanghai.net/cn/index.htm | cn.bing.com |
| 6 | 0.776 | 国内9家未上市GPU公司分析,我找到了“中国英伟达”! - 知乎 | https://www.jfdaily.com.cn/wx/detail.do?id=10 | www.baidu.com |
| 7 | 0.771 | 国内IDC机房托管服务商-提供国际T3+数据中心智算中心 | https://zhuanlan.zhihu.com/p/17259317189 | www.baidu.com |
| 8 | 0.768 | 国产算力消息:华为昇腾、阿里平头哥、沐曦、壁仞:四大国产GPU可以... | https://zhuanlan.zhihu.com/p/2014109606914303 | www.baidu.com |
| 9 | 0.767 | AI芯片厂商掀IPO热潮,谁能成为下一个“寒武纪”? \| 每经网 | https://www.nbd.com.cn/articles/2025-01-21/37 | www.sogou.com |
| 10 | 0.763 | 漫步上海 \| 16个超好玩的景点，一天就够了_澎湃号·湃客_澎湃 ... | https://www.thepaper.cn/newsDetail_forward_27 | cn.bing.com |

---
## LLM 深度分析

### 搜索引擎可用性（国内直连）

| 引擎 | 状态 | 说明 |
|------|------|------|
| 百度 (baidu.com) | ✅ 可用 | 中文内容覆盖优秀，国产GPU/大模型场景表现最佳 |
| 搜狗 (sogou.com) | ✅ 可用 | 中文技术内容好，PostgreSQL 官方文档命中率高 |
| Bing CN (cn.bing.com) | ✅ 可用 | 中英混合覆盖，但中文易触发百科/旅游污染 |
| Bing Intl (www.bing.com) | ⚠️ 偶尔可用 | 重定向到 CN，结果少，偶有股票论坛噪声 |
| Yandex | ❌ 不可达 | 连接被拒绝 |
| Yahoo | ❌ 不可达 | Network unreachable |
| Google | ❌ 不可达 | Playwright Chromium ICU 崩溃 (`icudtl.dat not found`) |

### 污染模式分析

1. **旅游污染** 🔴: `上海` 在 Bing CN 中触发旅游推荐（"上海景点"、"上海市文化和旅游局"）。场景3 Round 1/3 均出现。
2. **字典污染** 🟡: 单字被独立分词为字典条目（`壁`→"壁字的拼音"）。场景3 Round 2 出现。
3. **股票论坛污染** 🟡: `线程` 触发股票论坛帖子（"大智慧tv版"）。场景3 Round 2 出现。
4. **百科污染** 🟢: 百度百科条目偶尔混入（rrank 仍较低）。三场景均轻微出现。

### 嵌入重排效果

- **PostgreSQL 18**: re-rank 成功将官方文档 (0.850) 和深度技术文章 (0.849) 排到前面，百科/安装教程自动下沉
- **Claude Opus/Fable 5**: "Fable 5" 作为紧密专有名词，re-rank 分数高达 0.924，官方公告和深度解析排名靠前
- **上海GPU**: 尽管存在旅游污染，re-rank 仍将国产GPU新闻 (0.915, 0.888) 排在旅游结果 (0.756) 之前

### LLM 迭代策略效果

| 场景 | R1→R2 改进 | R2→R3 改进 |
|------|-----------|-----------|
| PostgreSQL 18 | 添加特征词 (AIO/UUIDv7) → 结果从通用变为精准特征文章 | 切换为官网域名锚定 → 命中官方文档和 Beta 公告 |
| Claude Opus/Fable | 添加 benchmark/swe-bench → 找到官方性能仓库但结果偏向公司概况 | 切换为 Fable 5 专有名词 → 结果高度精准 (sim 0.924) |
| 上海GPU | 切换为具体公司名（壁仞/摩尔线程）→ 精准但有字典/股票污染 | 扩展为全量厂商名（昇腾/沐曦/天数智芯）→ 覆盖面更全但旅游污染加重 |

### 核心结论

1. **国内直连环境下，百度+搜狗+Bing CN 三引擎组合可覆盖中英文搜索需求**，平均耗时 6-9s
2. **紧密专有名词是最佳反污染策略**：`Claude Fable 5`、`UUIDv7` 等不可分割的复合词重置了搜索意图
3. **中文城市名 + 技术关键词混合查询是高频污染源**：建议用公司名/产品名替代地名作为锚点
4. **嵌入重排是最有效的污染隔离层**：即使原始结果混入旅游/百科噪声，语义排序始终将相关内容推到前面
5. **Playwright Chromium 的 ICU 崩溃** (`icudtl.dat not found`) 导致 Google 引擎完全不可用，需修复 Playwright 安装
