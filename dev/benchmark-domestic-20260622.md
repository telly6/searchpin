# MiniSearch 搜索引擎基准测试 — 国内直连环境

> 测试时间: 2026-06-22 17:06
> 测试环境: macOS 宿主机直连（无 VPN / 无代理），国内网络
> 搜索策略: 每场景 3 轮纵深搜索迭代
> 嵌入模型: BAAI/bge-small-zh-v1.5

---

## 测试场景与查询

### PostgreSQL 18 数据库新版本
- R1: `PostgreSQL 18 release notes new features 2026`
- R2: `postgresql.org docs release 18 AIO async I/O OAuth uuidv7 virtual generated columns`
- R3: `"PostgreSQL 18" review benchmark AIO skip scan performance 2025`

### Claude Opus 5 / Fable 5 AI 模型发布
- R1: `Claude Opus 5 Anthropic latest model release 2026`
- R2: `Anthropic Claude Opus 4.8 release SWE-bench benchmark coding performance 2026`
- R3: `Claude Fable 5 Anthropic release model 2026`

### 上海 AI 算力 / 国产 GPU 芯片
- R1: `上海 AI算力中心 国产GPU芯片 2026年最新进展`
- R2: `国产GPU 砺算科技 壁仞 摩尔线程 2026 上市 7G100 BR100`
- R3: `上海智算中心 2026 GPU国产替代 昇腾 壁仞 沐曦 天数智芯 最新`

---

## 场景1_PostgreSQL18: PostgreSQL 18 数据库新版本

### 第 1 轮
```
Query: PostgreSQL 18 release notes new features 2026
Total: 3.69s | Search: 1.28s | Rerank: 2.41s | Merged: 24
Engines: cn.bing.com(4) + www.baidu.com(2) + www.sogou.com(4)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.850 | PostgreSQL 18 最新版本发布了,看看都有啥? - 墨天轮 | https://www.modb.pro/db/1971243032825573376 | www.baidu.com |
| 2 | 0.822 | PostgreSQL 18 Released: 3x Faster I/O Performance  | https://www.commandprompt.com/blog/postgresql-18-revolutiona | www.baidu.com |
| 3 | 0.816 | PostgreSQL: Release Notes | https://www.postgresql.org/docs/release/16.8/ | www.sogou.com |
| 4 | 0.809 | 【2025最新】PostgreSQL的安装、配置与使用指南 - 知乎 | https://zhuanlan.zhihu.com/p/1908417758892369241 | cn.bing.com |
| 5 | 0.804 | E. Release Notes - [ PostgreSQL 手册 ] - 在线原生手册 - ph | https://www.php.cn/manual/view/21026.html | www.sogou.com |
| 6 | 0.803 | PostgreSQL: 世界上最先进的开源数据库 - PostgreSQL 数据库 | https://postgresql.ac.cn/ | cn.bing.com |
| 7 | 0.789 | PostgreSQL: The world's most advanced open source  | https://postgresql.org/ | www.sogou.com |
| 8 | 0.787 | PostgreSQL: PostgreSQL 18 Released! | https://www.postgresql.org/about/news/postgresql-18-released | www.sogou.com |
| 9 | 0.783 | PostgreSQL：文档：18：PostgreSQL 18.0 文档 ... | https://postgres.ac.cn/docs/current/index.html | cn.bing.com |
| 10 | 0.770 | PostgreSQL_百度百科 | https://baike.baidu.com/item/PostgreSQL/530240 | cn.bing.com |

### 第 2 轮
```
Query: postgresql.org docs release 18 AIO async I/O OAuth uuidv7 virtual generated columns
Total: 5.3s | Search: 0.97s | Rerank: 4.33s | Merged: 24
Engines: cn.bing.com(1) + www.baidu.com(7) + www.sogou.com(2)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.880 | PostgreSQL v18发布,新增AIO uuidv7 OAuth等功能_postgresql  | https://blog.csdn.net/chensuiyi/article/details/156073158 | www.baidu.com |
| 2 | 0.797 | 揭秘PostgreSQL 18：新特性一览,数据处理将更高效！_操作_并行_... | https://www.sohu.com/a/865222527_122004016 | www.sogou.com |
| 3 | 0.790 | PostgreSQL 18 × MySQL 9.7 LTS 深度实战:异步I/O、虚拟生成列与... | http://chenxutan.com/d/2026.html | www.baidu.com |
| 4 | 0.787 | PostgreSQL 18 最新版本发布了,看看都有啥? - 墨天轮 | https://www.modb.pro/db/1971243032825573376 | www.baidu.com |
| 5 | 0.786 | 聚焦六大功能:PostgreSQL 18 新特性深度解析_postgresql 跳跃索引... | https://blog.csdn.net/mzl87/article/details/156953609 | www.baidu.com |
| 6 | 0.785 | PostgreSQL 18 深度解析:3倍I/O性能跃迁、虚拟生成列与云原生架构... | https://www.chenxutan.com/d/2019.html | www.baidu.com |
| 7 | 0.776 | PostgreSQL 18 已发布:一文读懂核心变化-腾讯云开发者社区-腾讯云 | https://cloud.tencent.com/developer/article/2586464 | www.baidu.com |
| 8 | 0.755 | 2025年9月25日:PostgreSQL 18 正式发布! - 哔哩哔哩 | https://www.bilibili.com/opus/1116878066051711014 | www.baidu.com |
| 9 | 0.749 | PostgreSQL: 世界上最先进的开源数据库 - PostgreSQL 数据库 | https://postgresql.ac.cn/ | cn.bing.com |
| 10 | 0.734 | PostgreSQL: The world's most advanced open source  | https://postgresql.org/ | www.sogou.com |

### 第 3 轮
```
Query: "PostgreSQL 18" review benchmark AIO skip scan performance 2025
Total: 4.98s | Search: 1.0s | Rerank: 3.98s | Merged: 23
Engines: cn.bing.com(1) + www.baidu.com(8) + www.sogou.com(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.838 | PostgreSQL 18 Released: 3x Faster I/O Performance  | https://www.commandprompt.com/blog/postgresql-18-revolutiona | www.baidu.com |
| 2 | 0.785 | PostgreSQL Performance Tuning Guide: Settings That | https://www.percona.com/blog/tuning-postgresql-database-para | www.baidu.com |
| 3 | 0.785 | Postgres 18:Skip Scan - 摆脱最左索引限制_postgres skip sca | https://blog.csdn.net/IvorySQL/article/details/155571796 | www.baidu.com |
| 4 | 0.765 | PostgreSQL 18 新特性解析(附一键安装脚本)-CSDN博客 | https://blog.csdn.net/qq_36936192/article/details/152115997 | www.baidu.com |
| 5 | 0.754 | PostgreSQL 18 Beta 1发布,有哪些功能亮点?-CSDN博客 | https://tonydong.blog.csdn.net/article/details/147811136 | www.baidu.com |
| 6 | 0.747 | PostgreSQL 18 正式发布,六大亮点特性! - 知乎 | https://zhuanlan.zhihu.com/p/1955713356955644491 | www.baidu.com |
| 7 | 0.744 | PostgreSQL v18发布,新增AIO uuidv7 OAuth等功能 - 知乎 | https://zhuanlan.zhihu.com/p/1985304642175914250 | www.baidu.com |
| 8 | 0.725 | Planet PostgreSQL | https://planet.postgresql.org/ | www.baidu.com |
| 9 | 0.724 | 【2025最新】PostgreSQL的安装、配置与使用指南 - 知乎 | https://zhuanlan.zhihu.com/p/1908417758892369241 | cn.bing.com |
| 10 | 0.720 | PostgreSQL 18新特性前瞻\|索引\|主键\|key\|优化器\|postgresql\|... | https://www.163.com/dy/article/JPGNQ7OP0511CUMI.html | www.sogou.com |

**PostgreSQL 18 数据库新版本 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~71 条 |
| 平均总耗时 | 4.66s |
| 平均搜索 | 1.08s |
| 平均重排 | 3.57s |
| 引擎参与 | cn.bing.com(6) + www.baidu.com(17) + www.sogou.com(7) |
| 平均 Top1 rerank | 0.856 |

---

## 场景2_ClaudeOpus: Claude Opus 5 / Fable 5 AI 模型发布

### 第 1 轮
```
Query: Claude Opus 5 Anthropic latest model release 2026
Total: 3.27s | Search: 1.06s | Rerank: 2.22s | Merged: 18
Engines: cn.bing.com(3) + www.baidu.com(5) + www.sogou.com(2)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.837 | Claude Opus \ Anthropic | https://www.anthropic.com/claude/opus | www.baidu.com |
| 2 | 0.791 | Home \ Anthropic | https://www.anthropic.com/ | cn.bing.com |
| 3 | 0.782 | Claude 中文版：Claude 4.5 国内使用指南～（支持 Claude ... | https://www.claudezh.com/claude/claude-chinese.html | cn.bing.com |
| 4 | 0.781 | claude opus5 | https://www.digitalocean.com/blog/whats-new-on-gradient-ai-p | www.baidu.com |
| 5 | 0.778 | Claude（Anthropic发布的大型语言模型）_百度百科 | https://baike.baidu.com/item/Claude/62812102 | cn.bing.com |
| 6 | 0.765 | Best AI Models for Claude Max | https://sourceforge.net/software/ai-models/integrates-with-c | www.sogou.com |
| 7 | 0.721 | Anthropic“光与影”双重奏:高喊AI风险的同时推顶尖模型 | https://www.zhihu.com/question/2043500165433185738/answer/20 | www.baidu.com |
| 8 | 0.712 | Home \ Anthropic | https://anthropic.com/ | www.baidu.com |
| 9 | 0.711 | Claude Fable 5正式发布:性能超越Opus 4.8?核心亮点与模型对比全... | https://www.zhihu.com/pin/2048442490223702797 | www.baidu.com |
| 10 | 0.711 | GlobalGPT: Your All-in-one AI, GPT-5.5, Claude Opu | https://www.glbgpt.com/ | www.sogou.com |

### 第 2 轮
```
Query: Anthropic Claude Opus 4.8 release SWE-bench benchmark coding performance 2026
Total: 4.56s | Search: 0.83s | Rerank: 3.73s | Merged: 14
Engines: cn.bing.com(6) + www.baidu.com(4)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.799 | Claude Opus 4.8(Anthropic推... - 百度百科 | https://www.anthropic.com/claude/opus | www.baidu.com |
| 2 | 0.770 | 刚刚!Claude Opus 4.8 炸场,一夜升级成工作流AI | https://adg.csdn.net/6a31124710ee7a33f27dd4b1.html | www.baidu.com |
| 3 | 0.754 | Claude Opus \ Anthropic | https://aieii.com/posts/2026-06-01-opus-48-vs-gpt55-benchmar | www.baidu.com |
| 4 | 0.753 | Anthropic凭什么把OpenAI拉下王座？\|美元_新浪财经_新浪网 | https://finance.sina.com.cn/wm/2026-05-13/doc-inhxtzpe070589 | cn.bing.com |
| 5 | 0.737 | MiniMax M3 对比 Claude Opus 4.8:SWE-Bench 差 10 分但便宜  | https://www.zhihu.com/question/2043500165433185738/answer/20 | www.baidu.com |
| 6 | 0.719 | Claude（Anthropic发布的大型语言模型）_百度百科 | https://baike.baidu.com/item/Claude/62812102 | cn.bing.com |
| 7 | 0.702 | 全球AI新王诞生，Anthropic估值冲爆1.2万亿，首次反超 ... | https://www.36kr.com/p/3799097984080899 | cn.bing.com |
| 8 | 0.685 | 从OpenAI出走，到成为AI独角兽：Anthropic诞生的完整故事 ... | https://news.qq.com/rain/a/20250409A09PHS00 | cn.bing.com |
| 9 | 0.682 | The AI for Problem Solvers \| Claude by Anthropic | https://claude.com/product/overview | cn.bing.com |
| 10 | 0.676 | Anthropic（美国人工智能股份有限公司）_百度百科 | https://baike.baidu.com/item/Anthropic/62639515 | cn.bing.com |

### 第 3 轮
```
Query: Claude Fable 5 Anthropic release model 2026
Total: 12.38s | Search: 10.76s | Rerank: 1.62s | Merged: 13
Engines: cn.bing.com(6) + www.baidu.com(4)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.980 | Claude Fable 5 Anthropic release model 2026 - 百度图片 | https://my.oschina.net/u/9487999/blog/19699920 | www.baidu.com |
| 2 | 0.881 | 仅仅间隔11天,Anthropic发布新一代通用大模型Claude Fable 5 | https://www.163264.com/12847 | www.baidu.com |
| 3 | 0.841 | Claude Fable 5 - 百度百科 | https://claude5.com/ | www.baidu.com |
| 4 | 0.800 | Claude Fable 5四日惊魂 | https://zhuanlan.zhihu.com/p/2047998267544360794 | www.baidu.com |
| 5 | 0.761 | Claude 中文版：Claude 4.5 国内使用指南～（支持 Claude ... | https://www.claudezh.com/claude/claude-chinese.html | cn.bing.com |
| 6 | 0.730 | Claude（Anthropic发布的大型语言模型）_百度百科 | https://baike.baidu.com/item/Claude/62812102 | cn.bing.com |
| 7 | 0.679 | Home \ Anthropic | https://www.anthropic.com/ | cn.bing.com |
| 8 | 0.673 | Download Claude \| Claude by Anthropic | https://claude.com/download | cn.bing.com |
| 9 | 0.648 | Claude AI是什么？它与ChatGPT相比如何？ - 知乎 | https://zhuanlan.zhihu.com/p/7761530703 | cn.bing.com |
| 10 | 0.608 | Claude | https://claude.com/ | cn.bing.com |

**Claude Opus 5 / Fable 5 AI 模型发布 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~45 条 |
| 平均总耗时 | 6.74s |
| 平均搜索 | 4.22s |
| 平均重排 | 2.52s |
| 引擎参与 | cn.bing.com(15) + www.baidu.com(13) + www.sogou.com(2) |
| 平均 Top1 rerank | 0.872 |

---

## 场景3_上海GPU: 上海 AI 算力 / 国产 GPU 芯片

### 第 1 轮
```
Query: 上海 AI算力中心 国产GPU芯片 2026年最新进展
Total: 30.37s | Search: 28.55s | Rerank: 1.82s | Merged: 12
Engines: cn.bing.com(8) + www.baidu.com(2)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.805 | 算力新变局\|深度 | https://xueqiu.com/5334485159/391039419?_ugc_source=ugcbaidu | www.baidu.com |
| 2 | 0.758 | 【2026最新】上海景點Top15必去.宮廷宴.外灘.武康路.上海 ... | https://kuolife.com/china-shanghai-attractions-mustgo/ | cn.bing.com |
| 3 | 0.753 | 【2026上海景點】自由行必讀!TOP16上海經典/熱門/新景點推薦 | https://gowithmarkhazyl.com/must-visit-places-in-shanghai/ | cn.bing.com |
| 4 | 0.743 | AI时代中国芯片突围战:硬核替代撞上“生态高墙”如何破局? | http://www.chinadevelopment.com.cn/news/cj/2026/05/1996075.s | www.baidu.com |
| 5 | 0.741 | 上海市_百度百科 | https://baike.baidu.com/item/%E4%B8%8A%E6%B5%B7%E5%B8%82/127 | cn.bing.com |
| 6 | 0.728 | 上海旅游指南和前往上海旅游-上海中国旅游官方网站 | https://www.meet-in-shanghai.net/tc/guide/ | cn.bing.com |
| 7 | 0.726 | 2025上海旅游全攻略：一年去了5次魔都！全都是避坑大实话 ... | https://zhuanlan.zhihu.com/p/23762942136 | cn.bing.com |
| 8 | 0.726 | 上海旅游必去十大景点游玩攻略，2025年11月魔都十大必去 ... | https://zhuanlan.zhihu.com/p/1974438659978720949 | cn.bing.com |
| 9 | 0.724 | 上海市文化和旅游局，上海中国官方旅游网站，上海旅游网站 ... | https://www.meet-in-shanghai.net/tc/ | cn.bing.com |
| 10 | 0.719 | 漫步上海 \| 16个超好玩的景点，一天就够了_澎湃号·湃客_澎湃 ... | https://www.thepaper.cn/newsDetail_forward_27506127 | cn.bing.com |

### 第 2 轮
```
Query: 国产GPU 砺算科技 壁仞 摩尔线程 2026 上市 7G100 BR100
Total: 60.14s | Search: 59.13s | Rerank: 1.01s | Merged: 28
Engines: www.baidu.com(5) + www.sogou.com(5)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.927 | 国产GPU性能逼近RTX 4060,2026年初消费级产品上市_显卡_什么值得买 | https://post.smzdm.com/p/a3m6rx0n/ | www.baidu.com |
| 2 | 0.907 | 壁仞科技首款通用GPU芯片BR100系列一次点亮成功-全球半导体观察 | https://www.dramx.com/News/IC/20220401-31182.html | www.sogou.com |
| 3 | 0.907 | 国产GPU终于要来了!砺算这次真的要打破海外垄断? - 知乎 | https://zhuanlan.zhihu.com/p/2013854197519503480 | www.baidu.com |
| 4 | 0.898 | 国产GPU上市潮:赛道火热背后,是真实力还是资本泡沫?-格隆汇 | https://www.gelonghui.com/p/3494024 | www.baidu.com |
| 5 | 0.894 | 770亿晶体管的中国第一算力通用GPU芯片！壁仞科技BR100亮相海外-... | https://news.mydrivers.com/1/854/854559.htm | www.sogou.com |
| 6 | 0.893 | 摩尔线程、壁仞科技,别上当了,带你看懂国产GPU谁更有价值? - 今... | https://www.toutiao.com/article/7477422930826953266/ | www.sogou.com |
| 7 | 0.882 | 国产GPU新动作,砺算7G100 GPU现已对客户出样,号称对抗RTX ... | https://www.bilibili.com/video/BV18TCXB6EHP/?spm_id_from=333 | www.sogou.com |
| 8 | 0.879 | 自主研发BR100的壁仞科技,打破全球算力纪录,2023年IPO谋新篇 - ... | https://www.toutiao.com/article/7257307858222498339/ | www.sogou.com |
| 9 | 0.868 | 国产GPU新秀砺算获5亿元融资:营收为零,投前估值35亿元!\|gpu\|显卡\|... | https://m.163.com/dy/article/K8C1HKMB0511838M.html | www.baidu.com |
| 10 | 0.868 | 国产GPU上市潮:赛道火热背后,是真实力还是资本泡沫?_财富号_东方... | https://caifuhao.eastmoney.com/news/20260104185812329428000 | www.baidu.com |

### 第 3 轮
```
Query: 上海智算中心 2026 GPU国产替代 昇腾 壁仞 沐曦 天数智芯 最新
Total: 2.96s | Search: 1.24s | Rerank: 1.72s | Merged: 27
Engines: cn.bing.com(5) + www.baidu.com(4) + www.bing.com(1)
```

| # | Rerank | Title | URL | Engine |
|---|--------|-------|-----|--------|
| 1 | 0.915 | 国产GPU大爆发,上海成最大赢家!\|智芯\|gpu\|上海市_网易订阅 | https://www.163.com/dy/article/KIRBRO760511DLVT.html | www.baidu.com |
| 2 | 0.868 | 国产算力的“上海时刻”:GPU企业密集上市,上海“芯”势力崛起... | https://caifuhao.eastmoney.com/news/20260112171845622877340 | www.baidu.com |
| 3 | 0.847 | AI算力竞速(中):国产GPU企业的集体冲锋与隐忧_腾讯新闻 | https://view.inews.qq.com/a/20260211A032C200 | www.baidu.com |
| 4 | 0.763 | 上海仪电助力构建高水平智算云服务体系 上海市智算产业高质量发展... | https://www.shanghai.gov.cn/nw31406/20260206/8a5501add55644c | www.baidu.com |
| 5 | 0.763 | 南部档案 国际版 第1集-电视剧-高清视频在线观看-芒果TV | https://www.mgtv.com/b/878850/24426686.html | cn.bing.com |
| 6 | 0.760 | DeepSeek \| 深度求索 | https://www.deepseek.com/ | www.bing.com |
| 7 | 0.753 | 热映《南部档案》免费观看全集在线播放 | https://kandian.sina.com.cn/article_7857201856_1d45362c00190 | cn.bing.com |
| 8 | 0.736 | 《南部档案》 - 短剧高清在线观看 \| 西瓜视频 | https://m.ixigua.com/dx/7651270375480839430 | cn.bing.com |
| 9 | 0.732 | 《南部档案》全集在线观看-电视剧星辰影院 | https://kandian.sina.com.cn/article_7857201856_1d45362c00190 | cn.bing.com |
| 10 | 0.731 | 《南部档案》-电视剧免费在线全集观看-太和影院 | https://www.taihe100.com/v/49465.html | cn.bing.com |

**上海 AI 算力 / 国产 GPU 芯片 汇总:**

| 指标 | 值 |
|------|-----|
| 轮次 | 3 |
| 累计合并 | ~67 条 |
| 平均总耗时 | 31.16s |
| 平均搜索 | 29.64s |
| 平均重排 | 1.52s |
| 引擎参与 | cn.bing.com(13) + www.baidu.com(11) + www.bing.com(1) + www.sogou.com(5) |
| 平均 Top1 rerank | 0.882 |

---

## 引擎参与总览

```
  cn.bing.com     ████████████████████████ 34 条
  www.baidu.com   ██████████████████████████████ 41 条
  www.bing.com    █ 1 条
  www.sogou.com   ██████████ 14 条
```

## 整体总结

- 平均总耗时: ~14.18s
- 可用引擎: 4 个
- 总引擎参与: 90 条

## 环境配置记录

```
测试环境: macOS 宿主机
网络: 国内直连 (无 VPN / 无代理)
搜索后端: Multi-engine (Sogou + Baidu + Bing CN + Bing Intl + Google + Yahoo + Yandex)
策略: 每场景 3 轮纵深迭代
嵌入模型: BAAI/bge-small-zh-v1.5
```