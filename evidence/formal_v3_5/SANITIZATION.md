# 协作快照脱敏记录

本目录是正式 v3.5 关账证据的 GitHub 协作快照，不是本地原件的逐字节镜像。

## 唯一脱敏改动

5 份 O3 复核原始运输外壳的警告文本含本机绝对路径。协作快照将其中 20 处 `/Users/<local-user>/` 前缀替换为 `/REDACTED_USER_HOME/`。模型的判断文本、解析后有效 JSON、18 份编码、6 份合并复核、回答、映射和统计算法都未改。

## 哈希连接

- 本地关账原件 `manifest_review.json`: `50b22d6ae17e57aab258d23762ac4fd3b59f2d6adbb45608881e1d4452fbaf55`
- 协作脱敏快照 `manifest_review.json`: `6b55b70b6c7cb71c133cfe76cc9fae2a809d2780e5385ccec665c74487ab1f8a`
- 本地关账原件 `manifest_results.json`: `c616e14fe218120dc1adfcd47558f481084d1e8b29d7a4637433821becc43be9`
- 协作脱敏快照 `manifest_results.json`: `709d9d3d23f32b3aa0b642a15915e23f7544310c3fd5eba53a70ea3a96e219b2`
- 两版 `summary.json` 均为 `d49be125db9ac42ea860a51f580270f93f2e83c3f34b41f48dba4f8e1a5062bf`
- 两版 `audit.json` 均为 `a9117b1d839c57adbde7598e0229f32694d145954ce1c2692d2453e78028683f`

原始本地证据仍由项目负责人按原哈希保管，不上传 GitHub。
