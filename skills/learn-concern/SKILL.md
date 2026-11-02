# Skill：关注点学习（learn-concern）

## 何时用
拿到一批新的问询函，要更新"监管关注点"本体。

## 输入
- `questions.json`：新公司的问询问题；
- `train_codes`：训练公司代码列表。

## 步骤
1. 跑 `tools/learn_concerns.py --train ...`，模型归纳 10 个关注点（名称/关键词/追问）；
2. 人工确认：去掉过窄、过宽、重复的；
3. 写入 `data/concerns_learned.json`，重跑 `tools/build_kg.py`。

## 输出
更新后的关注点清单 + 图谱重建结果（节点/边变化）。

## 不要做
- 不要跳过人工确认直接上线；
- 不要把某一家公司特有的问题当成通用关注点。
