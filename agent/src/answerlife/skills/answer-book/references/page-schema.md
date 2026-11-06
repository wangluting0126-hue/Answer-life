# JSON 输入约定 · 1.1

示例可直接复制 `examples/career.json`。文案字段全为纯文本，换行分段；HTML 会按字面显示，不作为标签执行。

| 字段 | 要求 |
|---|---|
| date | 必填，YYYY-MM-DD，用户时区日期 |
| no | 可选，书页编号，如 0001 |
| mode | 可选，quick / dialogue / dossier / review，默认 dialogue |
| theme | 必填，八主题中的一个 |
| issue_key | 必填，同一具体问题保持相同短 key，英文小写字母/数字/连字符 |
| quote | 必填，用户原话；模拟数据明确标记为演示 |
| title | 必填，暂定命名 |
| origin | 必填，文本坐标与相关处境 |
| gloss | 必填，白话讲解，换行分段 |
| context_note | 必填，原意与本次延伸的区别 |
| source_mode | 必填，bank 或 paraphrase |
| quote_id | bank 时必填；由库注入原文和出处 |
| source_work / source_note / source_text | paraphrase 时必填，分别为书名/来源情况/间接转述；没有可靠书意用“本页借读” |
| dissent | 必填，异议及其适用边界 |
| dissent_quote_id | 可选，第二条库引文；不能与主引文同作品 |
| dissent_work | 无第二条引文时必填，如“非暴力沟通”或“本页的另一个可能”；前者显示“书意转述，未引原文” |
| criterion | 必填，本次可观察的分流条件 |
| action | 必填，7 天实验；用户不想行动可写成“如果愿意……” |
| question | 必填，一句反问 |
| action_status | 可选，unknown / planned / done / skipped，默认 unknown |
| action_result | 可选，用户回报的结果，不能由模型补造 |
| behavior_unchanged | 可选，true / false / null；只有用户明确说行为没变才为 true |

禁止输入 `original`、`cite`、`source_url`、`source_line`、`works`；这些由程序决定。未知字段拒绝，拼错字段不会默默丢失。

卷宗格式：`{"chapter_title":"这一章的名字","pages":[…]}`，2–3 页。渲染器处理页面结构和注入库引文；内容质量由 skill 与读源核验负责。

`render` 输出 `.html`、`.md`、`.json`。JSON 是规范化输入与来源快照，包含当前问题的个人内容；与 HTML 一样由用户决定保存、分享和删除，不自动记录历史。不覆盖已有文件，确需重生成时使用 `--force`。

## 1.1 可选的 assessment

该对象只支持 `facts`、`possibilities`、`unknowns` 三个文本数组与 `next_check` 非空文本。前两项至少各一条；unknowns 可为空。HTML 中作为可展开的“这一页依据什么”，不增加正文负担。旧输入不需要补该字段。示例见 [reasoning.md](reasoning.md)。字段校验不能证明判断准确。
