# 文献勘察·任务 2 抢先权检查(Claude 侧独立轮)

> **锚定防护:本文件暂存本地,lingyun 的独立轮交付前不入仓库、不在 Issue/PR 提及。**
> 交付后作为第二独立轮与其对照,一致处增信,分歧处逐条核。

## 执行环境声明

- 执行者:Claude Fable 5(项目负责人会话内),全部页面由本执行者实际联网打开
- 执行日期:2026-07-29
- 模型辅助部分:12 路并行 WebSearch 由 workflow 子代理执行(检索与初筛);
  **全部候选的判定均由本执行者亲自打开页面核验**,子代理只提供线索
- 检索源(3 个成功 + 1 个失败如实登记):
  1. WebSearch(Google 索引)×12 主查询串 + 各至多 1 次变体,每路阅约 15–20 条结果
  2. arXiv API ×5 查询
  3. OpenAlex API ×2 查询(无相关命中,如实记)
  4. Semantic Scholar API ×3 次尝试**全部 429 限流,未获数据**——本轮未覆盖该源
- 正文条目是否有未经本执行者打开页面的:**无**(逐条档位见下)

## 一句话交付

**在本轮登记范围(2024-01—2026-07;上述三源;下列查询串)内,未检出 5/5 抢先研究;
一条曾达摘要级 4/5 的最强候选经正文核验后判 3/5,归入相关工作。方向存活。**

## 任务 2 判定

### 判定为「相关工作」的核验候选(全部本人打开页面)

| 论文 | 档位 | A-i | A-ii | A-iii | A-iv | A-v | 计 | 判定 |
|---|---|---|---|---|---|---|---|---|
| **Wohn et al. 2026,"Are we writing an advice column for Spock here?" Understanding Stereotypes in AI Advice for Autistic Users,CHI '26,arXiv:2601.12690** | **【原文核】** | ✓(§3.1 Step5:披露自闭症 vs 不披露,5 种措辞×10 次) | **✗**(§3.1 Step5–6:因变量是二选一选项的**推荐频率漂移**(ST–AST / AT–NA gap),不是回答覆盖角度的数量或分布) | ~(§4.2–4.4:11 名自闭症参与者作**规范性判断**,结论混合:"有用"与"幼儿化/限制成长"并存;非正式的有用性评分) | ✓(§4.2:目标用户本人) | **✗**(场景为二选一决策题"Should I do A or B",非多角度开放生成) | 3/5 | 相关工作(**本轮最重要前驱**) |
| Kantharuban et al. 2024/2025, Stereotype or Personalization? User Identity Biases Chatbot Recommendations, arXiv:2410.05613 v2 | 【元数据核】 | ✓ | ✗(测偏见存在与不透明,非窄化计数) | ✗ | 摘要未明 | ~(推荐任务) | ≤2/5 | 相关工作 |
| Karadal & Kekulluoglu 2025, ChatGPT Response Differences Based on Inferred Political Orientation, arXiv:2511.04706 | 【元数据核】 | ✓(三 persona 含中性) | ✗(定性分析措辞与论证,不量化宽度) | ✗ | ✗(作者定性) | ✓ | 2/5 | 相关工作(**机制上最近:用的就是 ChatGPT memory 与 custom instructions**) |
| Yao 2026, More Is Not More: What Matters for Diversity in LLM Opinions?, arXiv:2607.20429 | 【元数据核】 | ✓(persona 细节分级 vs 基线) | ✓(多指标量化 100 道开放题的观点多样性;"人口属性触发刻板化收窄") | ✗ | ✗(纯计算指标) | ✓ | 3/5 | 相关工作(**A-ii 的直接方法学前驱**;单一作者、仅 arXiv,引用需谨慎) |
| Lutz et al. 2025, The Prompt Makes the Person(a), EMNLP Findings 2025, arXiv:2507.16076 | 【元数据核】 | 摘要未明 | 摘要未明(检索线索称语义多样性下降,摘要未证) | ✗ | 摘要未明 | ✓ | 疑似 ≤3/5 | 相关工作(待正文升档) |
| Tao et al. 2025, PersonaFeedback, arXiv:2506.12915 | 【元数据核】 | 摘要未明 | ✗ | ✓(8298 人类标注) | 标注者身份未明 | 未明 | ≤3/5 | 相关工作(检索线索称 54.6% 个性化回答不优于通用,**待正文核**) |

### 结论(按规格措辞纪律)

- **未找到**(定义:【原文核】且 4/5 或 5/5 的最终判定)。
- 唯一逼近者 CHI '26 自闭症建议论文,**正文核验后在 A-ii 与 A-v 两要素上明确不满足**:
  它测"披露身份后二选一推荐向刻板方向漂移多少",不测"开放回答覆盖的角度变少多少"。
- **本项目的缺口经此轮收窄后仍然成立**:中性学科身份标签 + 开放多角度问题 +
  角度覆盖的数量/分布测量 + (下一步)目标用户价值评价——四者同时,本轮范围内未检出。

### 对 Issue #5 拍板的三条直接输入

1. **CHI '26 那篇是"变窄好不好"问题的可发表性证明**:同类问题(身份→建议收窄→
   目标用户怎么看)已进 CHI,且其用户结论是**混合的**——预示我们的价值研究很可能
   也得到异质结果,预注册必须预设"分歧也是发现"的结局分支。
2. **arXiv:2511.04706 证明"memory/custom-instructions 推断身份改变回答"已有人做**,
   但停在定性;我们的量化两本账是增量。
3. **arXiv:2607.20429 已在纯计算指标上测到"人口属性触发刻板化收窄"**——与我们
   主结果同向,可作跨方法佐证;但它没有人类判官、没有价值判断。

## 检索词表(全部登记)

WebSearch 12 主串 = 规格种子 10 条 + `user background label LLM narrower answers user satisfaction study` + `personalized AI assistant reduces answer perspectives target user rating` + `memory personalization LLM open-ended advice diversity human judges`(每路另至多 1 次变体,见 workflow 日志 wf_82809761-7fa);
arXiv API 5 串:personalization+response diversity / persona+diversity+human evaluation(cs.CL) / echo chamber+personalization / viewpoint diversity+LLM / user identity+recommendations+stereotype;
OpenAlex 2 串:persona identity disclosure advice narrowing / personalization response diversity reduction human study。

## 待核清单(【仅检索命中】,未打开)

Personalized Reasoning (arXiv:2510.00177,"29% 个性化尝试差于通用");User Perceptions vs. Proxy LLM Judges (arXiv:2510.20721,**任务 3 高相关**:真人与 LLM 判官在 helpfulness 上不一致);Evaluating LLM Adaptation to Sociodemographic Factors (arXiv:2505.21362);LLMs...flatten identity groups (arXiv:2402.01908);Helpful assistant or fruitful facilitator (PLOS One 2025);Can LLM be a Personalized Judge? (arXiv:2406.11657,任务 3);Dialect vs Demographics (arXiv:2604.21152);AgentAda (arXiv:2504.07421)。

## 范围与局限

Semantic Scholar 未覆盖(限流);中文文献未系统检索(WebSearch 中文串仅经种子词);
Google Scholar 未单独作为源(与 WebSearch 部分重叠);待核清单 8 条未开卷。
lingyun 独立轮交付后对照,分歧处以正文核验裁决。
