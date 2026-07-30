# 文献勘察结果（第一轮）

## 执行环境声明

- **执行主体**：OpenAI Codex。
- **执行日期**：2026-07-29。
- **人工部分**：用户审定了检索目标、检索计划和本轮返工边界；Lingyun 于 2026-07-30 本人打开全部官方页面及指定正文页，逐项复核了书目信息、关键论断位置和报告中的具体论文数字，13 项均一致，无差异或未找到项；没有把聊天中的判断直接当作论文证据。
- **模型辅助部分**：Codex（GPT-5；当前运行环境没有向执行者暴露更细的模型快照编号）负责读取仓库、执行查询、打开正文、提取证据位置和撰写；并用同类 Codex 子任务分别复核规格、PR 范围和论断位置。
- **检索源**：arXiv API、ACL Anthology 官方 XML、OpenReview API、OpenAlex API，以及论文官方落地页和正文。
- **正文核验方式**：正文表中的论文均由本轮执行主体实际打开 PDF，并定位到节号、图号或表号；PDF 只用于本地核验，不进入仓库。
- **是否有正文条目未由执行主体打开页面**：**无**。没有打开正文的线索只进入文末 `【仅检索命中】` 待核清单。
- **检索复算边界**：arXiv 计数使用 `submittedDate:[202401010000 TO 202607312359]` 并检查相关性排序前 20 条；ACL 计数来自官方 XML 的题名与摘要，版本为 [`acl-org/acl-anthology@3e66e6c`](https://github.com/acl-org/acl-anthology/commit/3e66e6cbe2702587e1a751353632ce4116f99122)；OpenReview 计数是 API 返回记录按发布日期过滤到 2024-01—2026-07 后的记录数，可能含重复论文、评审或评论；OpenAlex 计数是元数据全文搜索结果，召回很宽，只作补充。
- **“有用条数”的定义**：检查结果后，进入本报告正文或文末待核清单的去重论文数；不是“看起来相关”的结果总数。
- **访问失败**：Semantic Scholar API 返回 HTTP 429；ACM Digital Library 被 Cloudflare 挡住；Google Scholar 和 ACL 网页搜索在浏览器自动化中超时；OpenReview 网页触发反自动化验证。它们都没有被伪记成“0 命中”，也没有用于支持“未检出”的强结论。
- **计数复算限制**：动态 API 的命中数是 2026-07-29 当日快照。本报告保留了查询串、时间窗和 ACL XML 的版本，但没有保存 API 原始响应或可执行计数脚本；未来重跑时数字可能变化。因此这些数字只说明本轮查了多宽，不作为论文结论或抢先权判定的证据。

### 本项目的冻结边界

本项目当前的**观察**只适用于：单一 Claude Opus 4.6；主检验仅 `S2`、`S10′` 两题，各独立生成 6 次，共 12 个主块；`S8′` 是 `PILOT_ONLY` 线索的 4 块重测，未过 `3/4` 门槛，不能和主结果混写；背景注入也只有一种逐字措辞，即 `已知用户背景：用户是数学系本科生。`；Claude Max / Claude Code CLI 通道的温度、最大输出等订阅层参数不可控；全部编码由 AI 完成；三名人类判官只做关账后的校准。人类联合分数与冻结 AI 联合分数逐块一致 10/12，状态为 `calibration_supported`，但回答可能显露数学身份，因此不是完全双盲，也不是独立复制。证据见 [`文献检索执行规格 §背景`](../../docs/next-step/2026-07-27-文献检索执行规格-v1.md) 和 [`人类校验关账报告`](../../docs/human-validation/10_人类校验关账报告_2026-07-24.md)。

本项目当前的**解释边界**是：冻结实验观察到回答组织方向发生变化，但没有证明模型内部机制，也没有检验“更数学”对数学本科生究竟更有帮助还是更受限制。这个价值问题仍是下一步问题，不是已经得到的结果。

三个对比回答的问题不同，后文一律使用以下口径：

| 对比 | 准确含义 |
|---|---|
| `M−N` | 数学本科生背景 vs 无背景；最接近原使用体验中的总观察差异 |
| `M−G` | 数学本科生背景 vs 一般本科生背景；数学标签相对一般背景的额外作用 |
| `G−N` | 一般本科生背景 vs 无背景；只要加入一般背景是否就会变化 |

口径出处：[`正式实验关账后方法澄清 §4`](../../docs/method/16_正式实验关账后方法澄清_2026-07-26.md)。

## 任务 1 · 七篇精读

### 1. Fang et al. (2026), *The Personalization Trap*

论文：[ACL Anthology](https://aclanthology.org/2026.acl-short.43/)

- **研究问题（观察）**：同一道本应与用户身份无关的情绪理解题，在系统记忆中加入不同社会人口画像后，模型判断是否会改变；论文同时问这种影响是否因画像和模型而异。`【原文核：§1，RQ1–RQ3】`
- **方法（观察）**：作者构造优势／弱势成对画像和交叉人口画像，把画像注入系统提示，再在经过人类筛选的情绪理解与管理题上比较无记忆和有记忆条件。`【原文核：§2.1–§2.2、§3】`
- **可借用（本项目解释）**：可以借用“题目内容保持不变，只改变背景”以及“先由人判断哪些题理论上不应受画像影响”的控制思路；这能减少把合理个性化误判为干扰。`【原文核：§2.2、§3 的 Human Annotation】`
- **与本项目的差别（本项目解释）**：它主要测固定答案情绪题的正确率和答案翻转，不测一条开放回答内部少了多少非数学路径，也没有让目标用户判断这种变化是否有用。`【原文核：§2.2、§3、§4】`

### 2. Weeber et al. (2026), *One Persona, Many Cues, Different Results*

论文：[ACL Anthology](https://aclanthology.org/2026.acl-long.2079/)

- **研究问题（观察）**：同一人口属性用姓名、显式陈述、真实或合成对话历史等不同方式表达时，模型行为和研究结论是否稳定。`【原文核：§1、§3.1–§3.2】`
- **方法（观察）**：论文交叉组合多种 persona cue、人口属性、模型和任务，并加入无 persona 基线；先比较不同 cue 的结果相关性，再比较不同 persona 的结果差异。`【原文核：§3.1–§3.4、§4、§5.1–§5.2】`
- **可借用（本项目解释）**：下一轮不能只重复一句背景；应预注册数种语义等价但形式不同的背景表达，并把“措辞 × 标签”的交互作为稳健性检查。`【原文核：§3.2、§5.1–§5.2】`
- **与本项目的差别（本项目解释）**：论文多数任务是封闭式判断，开放写作只占一部分；它比较 cue 对输出或群体差异的影响，没有测单回答路径收窄，也没有目标用户价值评价。`【原文核：§3.3、§4、§5】`

### 3. Zhang, Liu & August (2026), *Re-Centering Humans in LLM Personalization*

论文：[arXiv](https://arxiv.org/abs/2606.06614)

- **研究问题（观察）**：真实对话中的用户属性能否被可靠抽取、哪些属性应影响当前问题，以及个性化回答是否真的比通用回答更受人类欢迎。`【原文核：§2、§3】`
- **方法（观察）**：作者把个性化拆成属性抽取、相关性选择和回答生成三阶段；用真人对话和三名人类标注员分别判断属性、相关性及个性化回答相对通用回答的偏好，并与多个 LLM 判官比较。`【原文核：§4.1、§5.1、§6.1、附录 G】`
- **可借用（本项目解释）**：最可借用的是三阶段拆分，以及在生成前让人判断“这个属性是否应影响这道题”；生成后的价值评价必须与结构编码分开。`【原文核：§2、§5、§6】`
- **与本项目的差别（本项目解释）**：它使用从对话历史提取的多项属性，而不是单一句数学身份标签；价值判断由通用众包标注员完成，不是被个性化的原用户；也没有测单回答路径数量。`【原文核：§4.1、§6.1、附录 G】`

### 4. Fisher, Neville & Park (2026), *Response-Aware User Memory Selection for LLM Personalization*（RUMS）

论文：[arXiv](https://arxiv.org/abs/2604.14473)

- **研究问题（观察）**：选择用户记忆时，能否不用“问题与记忆的表面相似度”，而根据记忆实际怎样改变模型的回答分布来选。`【原文核：§1、§3】`
- **方法（观察）**：RUMS 用加入记忆前后的预测熵差作为代理效用，选择效用最高的记忆子集；低于阈值时可以选空集，再训练轻量模型近似该选择过程。`【原文核：§3.1–§3.4】`
- **可借用（本项目解释）**：可以借用“允许不用任何记忆”的空集决策，以及把“是否注入”和“注入哪条”显式拆开；这比无条件把背景塞进提示更接近真正的前门控。`【原文核：§3.4、§4.2–§4.3】`
- **与本项目的差别（本项目解释）**：熵下降只是用户效用的代理，论文自己也把“模型概率分布与人类效用对齐”列为必要假设；主要下游质量评价仍依赖 GPT-4 判官，且研究的是多条记忆选择，不是单一身份标签造成的回答收窄。`【原文核：§3.2 的 Interpretation and Limitations、§4.4】`

### 5. Wu et al. (2024), *How Easily do Irrelevant Inputs Skew the Responses of Large Language Models?*

论文：[arXiv](https://arxiv.org/abs/2404.03302)

- **研究问题（观察）**：不同语义相关程度、数量和问题形式的无关信息，会在多大程度上让模型偏离原本可由参数记忆回答的问题。`【原文核：§1、§3】`
- **方法（观察）**：作者先确认模型本来会答，再构造从完全无关到表面相关的干扰信息，分别测试自由回答和选择题，并用准确率及不确定性指标比较。`【原文核：§3.1–§3.6】`
- **可借用（本项目解释）**：可借用“先确认无干扰时能做对”和“把无关程度分档”的设计；背景标签也应先由独立规则判断与题目是否相关，再研究其影响。`【原文核：§3.2–§3.5】`
- **与本项目的差别（本项目解释）**：它研究外部事实干扰对事实问答正确性的影响，不研究用户身份、开放建议的内容广度或目标用户价值。`【原文核：§3.1、§3.6、§4】`

### 6. Wu et al. (2025), *LongMemEval*

论文：[arXiv](https://arxiv.org/abs/2410.10813)

- **研究问题（观察）**：长期聊天助手能否从跨会话历史中提取、组合、按时间更新信息，并在历史没有答案时拒绝编造。`【原文核：§3.1–§3.3】`
- **方法（观察）**：论文构造多会话记忆基准，把问题拆成信息提取、跨会话推理、时间推理、知识更新和 abstention 等能力，再用统一的存储、检索和阅读框架比较系统设计。`【原文核：§3.2、§4.1–§4.2】`
- **可借用（本项目解释）**：可借用“问题不可由历史回答时应说不知道”的负控制，以及把记忆系统拆成写入、检索、读取三段来定位错误。`【原文核：§3.2、§4.1】`
- **与本项目的差别（本项目解释）**：它的 abstention 是“历史中没有答案时拒答”，不是“当前问题不需要用户背景时不用记忆”；主指标是长期记忆问答，不是开放回答路径或用户价值。`【原文核：§3.2–§3.3、§5】`

### 7. Salemi et al. (2024), *LaMP*

论文：[ACL Anthology](https://aclanthology.org/2024.acl-long.399/)

- **研究问题（观察）**：怎样用用户历史记录构建可复用的个性化语言模型基准，并比较不同检索增强方法。`【原文核：§1、§2】`
- **方法（观察）**：LaMP 把每个样本写成当前输入、目标输出和用户历史 profile，覆盖分类与生成任务；个性化方法从 profile 检索条目，再把检索结果注入模型。`【原文核：§2.1–§2.3、§3】`
- **可借用（本项目解释）**：可借用同一任务的无检索／有检索对照、按用户和按时间两种数据切分，以及把检索器本身作为独立实验组件。`【原文核：§2.2、§3、§4.2】`
- **与本项目的差别（本项目解释）**：LaMP 主要问个性化是否提高任务指标，生成任务使用参考文本指标；它不检验单一句身份标签是否减少同一回答中的可行路径，也没有相应目标用户的好坏判断。`【原文核：§2.3、§4.2–§4.3、§5】`

## 任务 2 · 抢先权检查

### 判定口径

- A-i：身份／背景标签注入与未注入回答对照。
- A-ii：测量**单条开放回答内部**角度、方向或方面的数量／分布是否减少。
- A-iii：因变量含质量、有用性或满意度。
- A-iv：由目标用户或有依据的用户代理评价。
- A-v：开放式生成。

`5/5` 才是“抢先”，`4/5` 是“近似抢先”，`≤3/5` 只算相关工作。

### 候选清单

| 论文 | 档位 | 链接 | A-i（位置） | A-ii（位置） | A-iii（位置） | A-iv（位置） | A-v（位置） | 命中数 | 判定 |
|---|---|---|---|---|---|---|---|---:|---|
| MirrorStories | 【原文核】 | [EMNLP 2024](https://aclanthology.org/2024.emnlp-main.382/) | ✓ `§2.1–§2.2、图 1`：个性化故事 vs 通用故事 | ✗ `§4、表 2`：SDI 比较故事类型的文本集合，不是单篇故事内方向数 | ✓ `§3、图 4`：满意、质量、参与和个人相关性 | ✓ `§3、附录 A.1–A.2`：个性化故事与同一评价者身份匹配 | ✓ `§2.1–§2.2`：自由生成短故事 | 4/5 | **近似抢先**；唯一缺 A-ii |
| Re-Centering Humans | 【原文核】 | [arXiv 2026](https://arxiv.org/abs/2606.06614) | ✓ `§6.1`：无上下文回答 vs 注入相关用户属性的回答 | ✗ `§6.1–§6.2`：只测偏好评分，没有回答内部广度量具 | ✓ `§6.1–§6.2`：人类比较哪一个回答更好 | ✗ `§6.1、附录 G`：三名通用众包标注员，不是画像原用户 | ✓ `§6.1`：开放回答生成 | 3/5 | 相关工作 |
| MyScholarQA | 【原文核】 | [ACL 2026](https://aclanthology.org/2026.acl-long.723/) | ✗ `§2.1–§2.3`：由论文形成复杂 profile 并生成行动，不是单一身份标签有／无 | ✗ `§4.2、表 4`：`NARROW` 指拟议行动过于具体，不是最终单回答路径计数 | ✓ `§4.1–§4.2`：用户满意度与错误主题 | ✓ `§4.1`：活跃研究用户评价自己的 profile、行动和报告 | ✓ `§2.2–§2.3`：开放生成行动和研究报告 | 3/5 | 相关工作；“窄”构念很近，但测量单位不同 |

### 抢先权结论

**观察**：在本轮登记范围内，没有发现达到 `5/5` 的已核正文；发现一项 `4/5` 的近似抢先工作 MirrorStories，缺失项是 A-ii“单条回答内部的收窄测量”。这意味着不能再写“未检出 4/5”，也不能写“没人做过”。`【原文核：MirrorStories §2–§4、表 2】`

**本项目解释**：本项目仍可能研究“标签是否减少一条回答中的实质路径”，但新颖性不在“身份个性化 + 开放生成 + 目标用户评价”这四项组合；MirrorStories 已覆盖这四项。本项目尚未做目标用户价值评价，因此也不能写成已经回答了完整五要素问题。

### 检索词表

除特别说明外，时间窗均为 2024-01—2026-07。

| # | 查询串 | 检索源 | 命中数 | 有用条数 |
|---|---|---|---:|---:|
| T2-A1 | `all:personalization AND all:"response diversity" AND all:"user study"` | arXiv API | 0 | 0 |
| T2-A2 | `all:personalization AND all:diversity AND (all:LLM OR all:"large language model")` | arXiv API | 782 | 1 |
| T2-A3 | `(all:persona OR all:"identity cue") AND (all:diversity OR all:coverage) AND (all:LLM OR all:"large language model")` | arXiv API | 335 | 1 |
| T2-A4 | `all:"over-personalization" AND (all:memory OR all:persona)` | arXiv API | 5 | 0 |
| T2-A5 | `all:"LLM-as-judge" AND (all:human OR all:agreement)` | arXiv API | 270 | 0 |
| T2-A6 | `(all:"memory selection" OR all:"memory retrieval") AND (all:relevance OR all:utility) AND all:personalization` | arXiv API | 14 | 3 |
| T2-C1 | `personaliz* AND (diversity OR coverage) AND (user OR human)` | ACL 官方 XML，题名+摘要 | 24 | 1 |
| T2-C2 | `(persona OR identity OR sociodemographic) AND (cue OR prompt) AND (generation OR response)` | ACL 官方 XML，题名+摘要 | 159 | 1 |
| T2-C3 | `(LLM-as-judge OR evaluator) AND (human OR agreement) AND (quality OR preference)` | ACL 官方 XML，题名+摘要 | 140 | 1 |
| T2-O1 | `HUMAINE` | OpenReview API，窗口内记录 | 24 | 1 |
| T2-O2 | `OP-Bench` | OpenReview API，窗口内记录 | 2 | 0 |
| T2-O3 | `Spotlighting` | OpenReview API，窗口内记录 | 73 | 1 |
| T2-X1 | `personalization response diversity user study` | OpenAlex API | 60,882 | 0 |
| T2-X2 | `identity cue large language model topic coverage` | OpenAlex API | 6,647 | 0 |
| T2-X3 | `over-personalization LLM user perception` | OpenAlex API | 14,976 | 0 |

OpenAlex 三条查询的命中量说明普通全文搜索非常宽，不适合单独承担抢先权判定。OpenReview 的“命中”是记录而不是去重论文，因此只把它当发现工具；最终判定只看打开后的论文正文。

## 任务 3 · 方法学

### 1. AI 判官与人类在“哪个回答更好”上的一致性

**观察**：没有一个可跨任务套用的“典型一致率”。在最接近本项目的 Re-Centering Humans 中，不同 LLM 判官与人类个性化质量评分的 Spearman 相关约为 `0.111–0.376`；Spearman 相关是把两组评分各自转成排序后再比较，越接近 `1`，排序越一致。这里最高值仍不到 `0.4`。`【原文核：附录 G，表 6】`

MirrorStories 中，GPT-4 与人类对故事满意度、质量、参与度和个人相关性的相关随指标和故事类型变化，范围为 `0.08–0.47`。`【原文核：附录 A.4.2，表 5】`

**本项目解释**：在“个性化是否更好”这种主观问题上，AI 判官可作为便宜的辅助量具，但现有证据不支持把它当作目标用户的替代品。相关系数也不能直接换算成本项目的逐块一致率。

### 2. 人类判官彼此在“哪个回答更好”上的一致性

**观察**：Re-Centering Humans 的三名标注员在个性化回答质量上，Spearman 相关为 `0.325`，加权 Cohen’s kappa 为 `0.310`。加权 Cohen’s kappa 会扣除偶然碰巧一致的部分，并让“只差一个等级”比“相差多个等级”受到更轻的惩罚。`【原文核：§6.1】`

较早的 NLG 方法论文指出，开放语言质量评价中的分歧部分来自口味、背景知识、个人假设、推理方式和注意细节；把所有分歧都当作噪声、只追求更高一致性，可能把任务过度约束。`【原文核：Amidei et al. 2018，§4、§5】`

**本项目解释**：约 `0.31–0.33` 是一个相邻任务中的具体估计，不是普遍阈值。下一步若测“对用户好不好”，应先做小规模可测性试验并保留分歧，而不是预设三名判官一定会收敛。`【原文核：Re-Centering Humans §6.1】`

### 3. 相同结构化规则是否会抬高一致性

**观察**：本轮没有找到一篇直接随机分配“共享同一规则”与“各自独立判断”、从而量出一致性被抬高多少的研究。MetricEval 区分可靠性与效度，并在多特质-多方法框架中把“同一方法让不同构念看起来更相关”称为 **method bias**；它提醒，高相关可以来自测量方法，而不一定来自真正相同的构念。`【原文核：Xiao et al. 2023，§3.2.2、§4.1.2、表 1–2】`

Amidei et al. 还给出一个直接例子：减少类别可以显著提高 kappa，但这种提高部分来自任务被简化，而不一定代表更完整地捕捉了语言质量。`【原文核：Amidei et al. 2018，§2】`

**本项目解释**：

- 对本项目有直接原文依据的风险名称是 **method bias（方法偏差）**，并进一步追问**构念效度**。
- `criterion contamination` 只在评分规则把待证明的结论本身写进标准时更合适；目前没有证据证明本项目一定发生了这种污染。
- 现有三人校准说明“按同一冻结规则可得到相近结构编码”，即规则条件下的可靠性支持；它不能独立证明该规则完整代表“语义广度”，更不能证明用户价值。

### 证据表

| 论文 | 档位 | 链接 | 正文位置 | 支撑哪条结论 |
|---|---|---|---|---|
| Re-Centering Humans in LLM Personalization | 【原文核】 | [arXiv](https://arxiv.org/abs/2606.06614) | `§6.1–§6.3、附录 G 表 6` | 人机一致性不高；人际一致性约为低到中等；偏好具有主体差异 |
| MirrorStories | 【原文核】 | [ACL](https://aclanthology.org/2024.emnlp-main.382/) | `§5、附录 A.4.2 表 5` | AI 与人类在不同主观指标上的相关度变化很大 |
| Evaluating Evaluation Metrics（MetricEval） | 【原文核】 | [ACL](https://aclanthology.org/2023.emnlp-main.676/) | `§2、§3.2.2、§4.1.2、表 1–2` | 可靠性不等于效度；method bias 与构念混合 |
| Rethinking the Agreement in Human Evaluation Tasks | 【原文核】 | [ACL](https://aclanthology.org/C18-1281/) | `§2–§5` | 高一致性不总是目标；规则简化可能抬高一致性并丢失真实分歧 |

### 检索词表

| # | 查询串 | 检索源与时间窗 | 命中数 | 有用条数 |
|---|---|---|---:|---:|
| T3-A1 | `all:"LLM-as-judge" AND all:human AND all:agreement AND all:"response quality"` | arXiv，2024-01—2026-07 | 0 | 0 |
| T3-A2 | `all:"inter-annotator agreement" AND all:"response quality" AND (all:preference OR all:personalization)` | arXiv，2024-01—2026-07 | 2 | 1 |
| T3-A3 | `(all:"method bias" OR all:"common method variance" OR all:"criterion contamination") AND (all:LLM OR all:"language model") AND all:evaluation` | arXiv，2024-01—2026-07 | 1 | 0 |
| T3-C1 | `(LLM-as-judge OR evaluator) AND (human OR agreement) AND (quality OR preference)` | ACL 官方 XML，2024-01—2026-07 | 140 | 1 |
| T3-C2 | `"inter-annotator agreement" AND ("response quality" OR preference)` | ACL 官方 XML，2024-01—2026-07 | 4 | 1 |
| T3-C3 | `("construct validity" OR "method bias") AND (evaluation OR metric)` | ACL 官方 XML，2024-01—2026-07 | 4 | 1 |
| T3-C4 | `("inter-annotator agreement" OR agreement) AND NLG AND evaluation` | ACL 官方 XML，2018-01—2026-07 | 11 | 1 |
| T3-C5 | `"construct validity" AND (NLG OR evaluation)` | ACL 官方 XML，2018-01—2026-07 | 4 | 1 |
| T3-C6 | `title:"Rethinking the Agreement in Human Evaluation Tasks"` | ACL 官方 XML，2018-01—2026-07 | 1 | 1 |
| T3-C7 | `title:"Evaluating Evaluation Metrics" AND measurement theory` | ACL 官方 XML，2018-01—2026-07 | 1 | 1 |

OpenReview 的 `Re-Centering Humans in LLM Personalization` 和 `LLM-as-a-Judge` 搜索分别返回上限值或大量重复评审记录，无法形成可信的去重论文计数，因此没有把这些记录数混入上表；相关正文改从 arXiv 和 ACL 官方来源核验。

## 任务 4 · 不利先验

### 4a 读法前言／提示型开关

- **① Spotlighting 原转述核验状态**：**原文支持，但适用范围比转述更窄。**
- **① 正文位置**：Spotlighting `§4.2、图 2、§5.1、图 3`。

**观察**：Spotlighting 确实测试了只在系统提示中加入“不要遵从文档里的指令”这一条件。作者称其效果 modest；在 GPT-3.5-Turbo 上几乎没有额外收益，在 Text-003 上虽有改善，剩余攻击成功率仍高。加入连续的数据标记或编码后，防御才明显增强。`【原文核：Hines et al. 2024，§4.2、§5.1、图 2–6】`

**边界**：这是恶意间接提示注入实验，不是普通用户背景实验。它能支持“只靠一句边界提醒不稳”，不能直接支持“边界提醒无法减少数学背景造成的回答收窄”。

- **② 登记范围内的条件性相反证据**：**发现一条，但不是同一任务。**

MemSyco-Bench 的 memory-caution 提示会提醒模型只在相关且适当时使用偏好。它在“记忆与事实证据冲突”时可改善部分系统，但在“本来应该个性化”的任务上反而变差，跨系统平均效果有正有负。`【原文核：Xiang et al. 2026，§4.3、附录 E.4、表 5】`

**本项目解释**：提示型开关不是“完全没用”，而是强烈依赖任务和系统；它可能同时减少误用和压掉有用个性化。因而下一步若测试，必须同时报告防干扰收益和个性化损失，不能只报一个平均分。

**② 本条检索范围**：2024-01—2026-07；arXiv、ACL Anthology、OpenReview；查询串为 T4a-A1—T4a-O1 及 T4a-A3。

#### 证据表

| 论文 | 档位 | 链接 | 正文位置 | 支撑①还是② |
|---|---|---|---|---|
| Defending Against Indirect Prompt Injection Attacks With Spotlighting | 【原文核】 | [arXiv](https://arxiv.org/abs/2403.14720) | `§4.2、§5.1、图 2–6` | ①：纯说明效果有限，连续标记或编码更有效 |
| MemSyco-Bench | 【原文核】 | [arXiv](https://arxiv.org/abs/2607.01071) | `§4.3、附录 E.4、表 5` | ②：提示型 caution 的收益与代价随任务、系统而变 |

#### 检索词表

| # | 查询串 | 检索源与时间窗 | 命中数 | 有用条数 |
|---|---|---|---:|---:|
| T4a-A1 | `all:spotlighting AND all:"prompt injection"` | arXiv，2024-01—2026-07 | 4 | 4 |
| T4a-A2 | `all:"ignore the following" AND all:"prompt injection"` | arXiv，2024-01—2026-07 | 0 | 0 |
| T4a-A3 | `all:MemSyco` | arXiv，2024-01—2026-07 | 1 | 1 |
| T4a-C1 | `"prompt injection" AND (delimiter OR boundary OR spotlighting)` | ACL 官方 XML，2024-01—2026-07 | 0 | 0 |
| T4a-O1 | `Spotlighting` | OpenReview API，2024-01—2026-07 窗口内记录 | 73 | 1 |

### 4b 注入前的相关性门控

#### 现状

**观察 1**：RUMS 已经能在生成前从多条用户记忆中选子集，并在效用低于阈值时选择空集；它不是在信息进入上下文后劝模型“别受影响”。`【原文核：RUMS §3.4、§4.2–§4.3】`

**观察 2**：Re-Centering Humans 把“属性是否应影响当前问题”单独做成人类标注任务。它发现语义相似并不足以代表个性化相关性，并用人类标签训练相关性选择器。`【原文核：§5.1–§5.3、表 3】`

**观察 3**：MemSyco-Bench 表明，错误不只发生在检索阶段；不少错误发生在相关信息已经取回之后，模型仍没能正确处理记忆、事实和时间冲突。`【原文核：§4.2、图 5】`

#### 瓶颈

1. **论文观察**：RUMS 用熵下降代理记忆效用，并明确依赖“模型概率变化与人类效用对齐”的假设。`【原文核：RUMS §3.2 的 Interpretation and Limitations】`
   **本项目推论**：不能把文本相似或熵下降直接当成“对这个用户有用”；门控阈值最终需要用户证据。
2. **论文观察**：Re-Centering Humans 中，人类的相关性判断并非完全一致，模型又倾向过度选择属性。`【原文核：Re-Centering Humans §5.1–§5.3】`
   **本项目推论**：门控器不能只报召回率，还应分别报告误注入和漏掉有用个性化。
3. **论文观察**：MemSyco-Bench 发现，即使取回了相关记忆，生成阶段仍可能错误处理记忆、事实和时间冲突。`【原文核：MemSyco-Bench §4.2、§4.4】`
   **本项目推论**：应分别测“门控有没有选对”和“模型有没有用对”，不能把两类失败合成一个分数。
4. **论文观察**：RUMS 的主下游比较使用 GPT-4 判官，人类检查只在附录中小规模进行。`【原文核：RUMS §4.4、附录 A.9】`
   **本项目推论**：现有用户价值证据仍薄弱，不能替代目标用户评价。

**本项目解释**：注入前门控值得作为候选干预，但文献没有证明它会在本项目的数学标签条件下恢复回答广度，也没有证明恢复广度一定提升用户价值。合理的下一步是把门控当实验条件，而不是先写成解决方案。

#### 证据表

| 论文 | 档位 | 链接 | 正文位置 | 支撑哪条结论 |
|---|---|---|---|---|
| RUMS | 【原文核】 | [arXiv](https://arxiv.org/abs/2604.14473) | `§3.1–§3.4、§4.2–§4.4` | 可选空集的响应感知门控；代理效用假设与评价限制 |
| Re-Centering Humans | 【原文核】 | [arXiv](https://arxiv.org/abs/2606.06614) | `§5.1–§5.3、表 3` | 语义相似不足；应以人类相关性判断训练选择器 |
| MemSyco-Bench | 【原文核】 | [arXiv](https://arxiv.org/abs/2607.01071) | `§4.2、§4.4、图 5、表 2` | 检索后仍会错误使用记忆，门控不是完整解法 |
| LongMemEval | 【原文核】 | [arXiv](https://arxiv.org/abs/2410.10813) | `§3.2` | 只支持“历史无答案时拒答”，不能冒充个性化相关性门控证据 |

#### 检索词表

| # | 查询串 | 检索源与时间窗 | 命中数 | 有用条数 |
|---|---|---|---:|---:|
| T4b-A1 | `(all:"memory selection" OR all:"memory retrieval") AND (all:relevance OR all:utility) AND all:personalization` | arXiv，2024-01—2026-07 | 14 | 3 |
| T4b-A2 | `all:"when not to use memory" AND (all:LLM OR all:personalization)` | arXiv，2024-01—2026-07 | 0 | 0 |
| T4b-A3 | `all:"selective memory" AND (all:LLM OR all:"language model")` | arXiv，2024-01—2026-07 | 17 | 2 |
| T4b-C1 | `("memory selection" OR "memory retrieval") AND relevance AND personalization` | ACL 官方 XML，2024-01—2026-07 | 0 | 0 |
| T4b-C2 | `("use memory" OR "ignore memory") AND (relevance OR selective)` | ACL 官方 XML，2024-01—2026-07 | 0 | 0 |

OpenReview 的完整题名查询 `Response-Aware User Memory Selection` 返回上限 `10,000` 条混合记录，`MemSyco` 返回 0 条；前者显然不是可解释的论文命中数，因此未并入上表，RUMS 和 MemSyco 改由 arXiv 原文核验。

## 待核清单（【仅检索命中】）

下表论文只在检索结果、API 搜索记录或 ACL XML 查询命中中见到；本轮没有打开它们的论文落地页或正文，因此统一标为 `【仅检索命中】`，也没有用它们支持上面的实质结论。

| 论文 | 链接 | 为何没打开 |
|---|---|---|
| The Chameleon’s Limit | [arXiv:2604.24698](https://arxiv.org/abs/2604.24698) | 群体 persona 多样性与本项目相邻，但优先级低于已达到 4/5 的 MirrorStories |
| Unpacking Human Preference for LLMs: Demographically Aware Evaluation with the HUMAINE Framework | [OpenReview](https://openreview.net/forum?id=kVaE2kYjtV) | 只在 OpenReview API 搜索记录中见到；论文网页触发验证，未打开落地页 |
| LMUnit: Fine-grained Evaluation with Natural Language Unit Tests | [arXiv:2412.13091](https://arxiv.org/abs/2412.13091) | 可能补充细粒度评价方法，但不是任务 3 三问的直接证据 |
| Position: What Are We Measuring? Rethinking Evaluation in Natural Language Generation | [ACL](https://aclanthology.org/2026.gem-main.79/) | 可能补充构念效度术语；本轮先使用已打开的 MetricEval |
| The Task Shield | [arXiv:2412.16682](https://arxiv.org/abs/2412.16682) | 可能提供 Spotlighting 的条件性反证，但未完成正文定位 |
| NetInjectBench | [arXiv:2607.10490](https://arxiv.org/abs/2607.10490) | 间接提示注入基准，和普通用户背景仍有机制距离 |
| Multi-Stage Prompt Inference Attacks on Enterprise LLM Systems | [arXiv:2507.15613](https://arxiv.org/abs/2507.15613) | 搜索命中，但题名显示更偏攻击而非边界提示效果 |
| Towards Root Memories | [arXiv:2606.23283](https://arxiv.org/abs/2606.23283) | 可能补充个性化检索，但未核是否允许“不使用记忆” |
| Memory Retrieval for Changing Preferences | [arXiv:2606.02976](https://arxiv.org/abs/2606.02976) | 可能补充偏好更新门控，但未打开正文 |
| BudgetMem | [arXiv:2511.04919](https://arxiv.org/abs/2511.04919) | 题名偏成本控制，未核是否涉及用户价值或错误注入 |
| Selective Memory Retention for Long-Horizon LLM Agents | [arXiv:2606.29178](https://arxiv.org/abs/2606.29178) | 可能补充选择性记忆，但未核其选择发生在写入、检索还是生成阶段 |

## 一句话交付

在本轮检索范围内仍未检出已有答案的问题，按重要性排序如下：

1. **身份标签让一条开放回答少了某些方向时，目标用户到底觉得这是帮助还是限制？** 本轮没有检出 `5/5` 论文；MirrorStories 是 `4/5` 近似抢先，唯一缺单回答收窄量具。（本条检索范围：2024-01—2026-07；arXiv、ACL Anthology、OpenReview、OpenAlex；查询串 T2-A1—T2-X3。）
2. **数学本科生本人会不会认为冻结实验观察到的变化有用？** 当前项目只测了结构方向，文献中的通用标注员也不能替代目标用户。（本条检索范围：2018-01—2026-07；arXiv、ACL Anthology；查询串 T3-A1—T3-C7，并精读 Re-Centering Humans、MirrorStories、MetricEval、Rethinking Agreement。）
3. **注入前门控能否减少无关背景影响，同时不压掉真正有用的个性化？** 现有工作证明可以选择空集，也证明门控和生成时仲裁都可能失败，但没有在“身份标签导致单回答收窄 + 目标用户价值”上完成验证。（本条检索范围：2024-01—2026-07；arXiv、ACL Anthology、OpenReview；查询串 T4b-A1—T4b-C2。）
4. **一句读法前言、连续资料标记和真正删除无关背景，三者在本项目中谁有效、代价是什么？** 安全文献和 MemSyco 说明提示效果依赖任务与系统，不能直接替本项目作答。（本条检索范围：2024-01—2026-07；arXiv、ACL Anthology、OpenReview；查询串 T4a-A1—T4a-O1。）
5. **冻结现象能否跨模型、题目、背景等义措辞和注入位置复现？** 本轮文献明确提示 cue 形式会改变结论，但当前项目只有一个模型、两道主检验题和一种背景措辞。（本条检索范围：2024-01—2026-07；任务 1 七篇精读及任务 2 查询串 T2-A1—T2-X3。）

因此，文献检索后最稳妥的下一步不是直接宣布“门控是解决方案”，而是另立预注册：先由目标数学本科生验证“收窄”的价值，再把无背景、原始注入、读法前言、注入前门控和“通用核心 + 可选个性化补充”作为可比较条件；冻结 v3.5 证据继续只读。
