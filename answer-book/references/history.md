# 本地记录与周/月回看

没有后台任务、远程数据库、自动上传或通知。skill 在对话里完成内容生成，Python 脚本负责确定性的存储与统计。首次长期记录先说明保存内容和目录并取得同意；生成页面本身已经会包含当前问题，不另作长期收集。

## 记录

`record --data page.json --home /用户指定目录` 在 `sessions/` 写一条 JSON，返回不可猜测的 session ID。只保存日期、主题、问题 key、命名、实验、状态和结果；默认不留整段原话、不留工资和家庭细节。要记录脱敏后的摘要，在 title/action 中处理。卷宗每页单独 record，避免同一会话批量膨胀频次。

新动作默认 unknown。用户明确答应做才 planned；明确做完才 done；决定不做才 skipped。用户做过不等于有效，结果单独记。

```bash
python3 scripts/answer_book.py update --home /记录目录 \
  --id AB-返回的ID --status done --result '发出三次询价，一位约了具体需求讨论'
python3 scripts/answer_book.py update --home /记录目录 \
  --id AB-返回的ID --unchanged yes
```

`--unchanged yes/no/unknown` 只在用户回报时更新，表示行为是否仍未改变。状态与行为变化相互独立。文件只能按已存在 ID 更新；不允许路径作为 ID。

## 回看

用明确的闭区间日期，默认用户所说的自然周或自然月；不要用执行主机日期推断。“本月”在 2026-11-05 即 11-01 到 11-05，未来记录不参与。脚本只读指定 home 下 sessions，不扫描其他目录。

`review --start 2026-11-01 --end 2026-11-05 --home /记录目录 --out review.json` 得到：实际覆盖范围、有效记录数、主题计数、问题 key 计数、各问题最近实验状态与结果、损坏文件清单。损坏记录不算进去，并明确披露；没有记录如实说没有，不编“今年第 N 次”。

只有同一 `issue_key` 在所选时间窗内至少 3 条、且该问题最新回报 `behavior_unchanged: true`，才标 `needs_experiment_review: true`。planned/unknown/skipped 都不能单独证明行为没变。

## 写回看页

先说清“在这 N 条已保存记录里”，再指出哪个具体问题重复。引用旧动作和真实结果；unknown 就问是否做过。可用本次与上一次差异提出一个待确认理解，不说“你一直在逃避”。

需要复盘时不再堆一本书的解释，围绕上次实验问一个问题。没有复发证据时可以按当前困惑翻一页。用户需要文件时将回看写成 `mode: review` 的标准页，仍有异议、判据与可选实验；`origin` 可以交代本次读到的文本坐标，频次放 `gloss` 中并限定时间窗。

不需要维护 themes.json 缓存；统计从 session 原始记录计算，避免缓存与原始数据打架。只读模式不修改历史。用户想清理时，可删除自己指定目录的对应 JSON；不在后台跨设备同步。
