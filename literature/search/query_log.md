# 查询日志

本文件保存本轮实际使用或在检索过程中扩展出的逻辑组合。它用于复查召回范围，不代表每条查询在每个数据库中都能原样使用；不同平台会按自己的语法调整引号、布尔运算和时间过滤。

## 1. 核心逻辑

```text
(personaliz* OR persona OR "user profile" OR memory)
AND ("response diversity" OR "topic coverage" OR narrowing OR "filter bubble")
AND (LLM OR "large language model")
```

```text
("identity cue" OR demographic prompt OR background label)
AND (generic OR baseline OR control)
AND "open-ended"
```

```text
("real users" OR user study OR satisfaction OR helpfulness)
AND personalization
AND (coverage OR restrictive OR diversity)
```

```text
(memory retrieval OR memory selection)
AND (relevance gate OR abstention OR "when not to use")
```

```text
(LLM-as-judge OR human evaluation)
AND (agreement OR validity OR self-preference)
```

## 2. 个性化、收窄与用户价值

```text
LLM personalization "response diversity" user study
persona narrowing perspectives "large language model"
"user profile" LLM "answer diversity" helpfulness
personalized LLM "human evaluation" generic response
personalized LLM "human evaluation" worse than generic
"identity cue" LLM "topic coverage" reduction
"filter bubble" "large language model" user study personalization
over-personalization harm user perception LLM
"demographic prompting" LLM response breadth diversity
personalized LLM "viewpoint diversity" human evaluation
persona prompt "semantic diversity" personalized response user study
("demographic" OR "identity") personalization LLM "information coverage" users
("user background" OR "persona cue") LLM "coverage" "human evaluation"
personalized open-ended LLM "restrictive" responses user study
personalized LLM answer "alternative perspectives" real users
```

## 3. 判官与评价有效性

```text
"LLM-as-judge" human agreement response quality open-ended generation
"LLM-as-judge" human agreement response quality
inter-annotator agreement "response quality" preference judgment LLM
"criterion contamination" annotation validity language model evaluation
"shared method variance" human AI agreement
codebook "forced choice" annotator convergence bias LLM
LLM judge "correlation with human" open-ended generation
```

## 4. 记忆筛选与干预

```text
memory retrieval "relevance gating" personalization LLM
"when not to use memory" abstention personalized LLM
selective memory injection LLM user profile filtering
spotlighting prompt injection delimiter defense effectiveness Hines 2024
system prompt "ignore the following" instruction boundary evaluation LLM
MemSyco memory caution intervention LLM memory irrelevant
```

## 5. 中文查询

```text
个性化 大模型 回答多样性 用户评价
大语言模型 身份 标签 回答 收窄 个性化
大模型 用户记忆 过度个性化 相关性 门控
大模型 个性化 回答 视角 多样性 人类评价
```

## 6. 题名、方法名与引文追踪

在主题检索后，又使用已发现论文的题名、作者、方法名、基准名和参考文献做定向追踪，主要包括：

- `MyScholarQA`；
- `MirrorStories`；
- `RPEval` / `RP-Reasoner`；
- `OP-Bench` / `Self-ReCheck`；
- `DRIFTLENS`；
- `RUMS`；
- `LongMemEval`；
- `Spotlighting`；
- `CarMem`；
- `MemSyco-Bench`；
- `MetricEval`；
- `PerSE`；
- `LUFY`。

## 7. 日志边界

本轮保留了查询串、最终去重语料和筛选决策，但没有保留每次搜索页面的原始 HTML、用户登录态或逐查询命中数。这是为了避免把会话数据、个人信息和不必要的网页快照提交到仓库。因此：

- 可以复核“查了什么”和“最后留下什么”；
- 不能据此重建严格的 PRISMA 流程图；
- 不能把 51 篇解释为所有搜索结果的总数，它是去重并经过相关性筛选后的研究语料。
