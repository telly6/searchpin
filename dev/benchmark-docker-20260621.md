# MiniSearch 搜索引擎基准测试 — Docker 环境

> 测试时间: 2026-06-21
> 测试环境: Docker `minisearch:dev`（Xvfb + headed Chromium）
> MCP 配置: `docker run -i --rm -v ... minisearch:dev`

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

| 指标 | 值 |
|------|-----|
| 返回结果 | 10 / 10 |
| 合并结果 | 15 |
| 总耗时 | 9.34s |
| 搜索耗时 | 6.46s |
| 重排耗时 | 2.89s |
| 引擎参与 | **Google(8) + Sogou(2)** |
| Top3 rerank | 0.91 / 0.88 / 0.86 |
| 污染告警 | 无 |
| 质量评价 | ✅ **优秀** — 命中 neon.com, postgresql.org 官方文档, pgpedia.info 等高质量来源 |

Top 结果摘要:
1. neon.com — PostgreSQL 18 New Features (0.915)
2. postgresql.org — 18.1 Release Notes (0.878)
3. pgpedia.info — PostgreSQL 18 (0.863)

---

### 场景 2: Claude Opus 5

| 指标 | 值 |
|------|-----|
| 返回结果 | 10 / 10 |
| 合并结果 | 15 |
| 总耗时 | 12.19s |
| 搜索耗时 | 6.50s |
| 重排耗时 | 5.68s |
| 引擎参与 | **Google(9) + Sogou(1)** |
| Top3 rerank | 0.83 / 0.71 / 0.71 |
| 污染告警 | 无 |
| 质量评价 | ✅ **良好** — 命中 anthropic.com 官方公告, linas.substack.com 综述, 多个独立评测来源 |

Top 结果摘要:
1. techjacksolutions.com — Claude Model Lineage 2026 (0.833)
2. linas.substack.com — Anthropic 2026: Every Claude Model (0.714)
3. simplified.com — Claude 5 Release Expectations (0.706)

---

### 场景 3: 上海 AI 算力 / 国产 GPU

| 指标 | 值 |
|------|-----|
| 返回结果 | 10 / 10 |
| 合并结果 | 19 |
| 总耗时 | 13.67s |
| 搜索耗时 | 7.45s |
| 重排耗时 | 6.22s |
| 引擎参与 | **Google(6) + Sogou(4)** |
| Top3 rerank | 0.77 / 0.76 / 0.74 |
| 污染告警 | 无 |
| 质量评价 | ✅ **良好** — 命中 cls.cn（财联社）, openaxo.com（产业研报）, 多家中文本土媒体 |

Top 结果摘要:
1. cls.cn — 国产GPU、光互连超节点齐亮相 (0.767)
2. idc-expo.com — 2026上海国际AI算力产业大会 (0.764)
3. openaxo.com — 2026中国国产AI芯片深度研判 (0.741)

---

## 引擎参与总览

```
Google  ████████████████████████  23 条 (场景1:8, 场景2:9, 场景3:6)
Sogou   ███████                   7 条 (场景1:2, 场景2:1, 场景3:4)
Baidu   (零)
Bing CN (零)
Bing Intl (零)
Yahoo   (零)
Yandex  (零)
```

## 底层诊断

| 引擎 | 原因 |
|------|------|
| Baidu | CAPTCHA — Docker 数据中心 IP 触发 wappass.baidu.com 验证码 |
| Bing CN | 代码 bug — `follow_redirects=False` 但 cn.bing.com 必 301 跳转 |
| Bing Intl | 架构落后 — HTML 完全 JS 化，0 个 `<a href=` 链接，需浏览器渲染 |
| Yahoo | CDN 不兼容 — `_http_get` 自定义 SSL 连接被边缘节点拒掉 500 |
| Yandex | CAPTCHA — 触发 showcaptchafast 验证 |
| Sogou | ✅ HTTP 直连可用 |
| Google | ✅ Playwright headed 浏览器可用 |

## 整体总结

- **3/3 场景成功**，无污染告警
- **实际可用引擎仅 2/7**（Google + Sogou）
- 英文技术查询 Google 主导，中文技术查询 Google+Sogou 混合
- 政策法规类中文查询（如前次测试）覆盖率极弱
- 平均总耗时 ~11.7s
- 平均 top3 rerank ~0.81
