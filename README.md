# 答案之书 · Answer Life

带着一个问题来，带着一页书和一件小事回去。

## 运行 Agent

最新版的网页、终端和 IM Agent 在 [agent/](agent/)，带有小鸟情绪记录、答案页、周报月报和个人资料。安装好 uv 后，可以先体验不需要密钥的网页演示。

```bash
cd agent
uv sync --locked
AI_PROVIDER=mock uv run --locked answerlife serve
```

打开 <http://127.0.0.1:8020>。完整启动和模型配置见 [Agent 使用说明](agent/README.md)。下面是原来可单独安装到 AI 客户端的技能及其演示。

通过简短对话，把一个具体的人生纠结放到有出处的书页旁边，留下一个新的视角、一条可验证的判据和一个七天小实验。

## 四种使用方式

- **快速翻页**：带来一句困惑，生成一张短答案页。
- **一起读**：通过几轮对话补齐事实，生成个性化阅读页。
- **专题卷宗**：围绕转折点，将两到三个问题写成一章。
- **周/月回看**：根据授权保存的本地记录，回到上次实验与实际结果。

## 先看示例

下载项目后，用浏览器打开 [开始阅读.html](开始阅读.html)。里面包含职业、时间、关系、专题卷宗和周回看五组虚构演示；每组都有 HTML、Markdown 和来源快照。

## 使用 skill

[answer-book/](answer-book/) 是完整的 skill 目录，入口为 [SKILL.md](answer-book/SKILL.md)。将整个目录放到你所用 AI 客户端支持的技能位置，再请求使用 `$answer-book`。

例如：

> 请用答案之书。我学了很多课程，但作品集一直没有开始，帮我翻一页。

个性化对话与文案由 AI 客户端完成；Python 只负责查引文、渲染和记录。它不是独立聊天应用，不需要内置 API Key。

## 本地运行

需要 Python 3.9 或更新版本，无额外 pip 依赖。

```bash
cd answer-book
python3 scripts/answer_book.py quotes --theme '自我与身份' --query '不器'
python3 scripts/answer_book.py render --data examples/career.json --out output/答案页.html
python3 scripts/verify.py
```

## 设计与验证

页面参考 [Life Designer](https://github.com/Jackychen-12/life-designer) 的纸面阅读、自然对话与克制排版，模板独立编写。详见 [设计说明](设计与验收/设计说明.md) 和 [验收说明](设计与验收/验收说明.md)。

20 项程序检查通过。本地浏览器截图验收受当前工具策略限制，未宣称已完成。57 条候选引文来自初始设计包，其中一条边栏概要已禁用；其余保留原始核验口径，未宣称全部重新校订。

历史仅在用户授权后保存于指定本地目录。示例为虚构素材，仓库不包含实际用户的个人求职会话或申请材料。
