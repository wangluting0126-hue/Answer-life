"""内置 skill 的程序化工具。每个模块导出 SKILL（对应的 skill 名）、SPECS（工具定义）和同名的处理函数。

只有这里的代码会被执行；从用户目录安装的第三方 skill 只提供说明文字。
"""

from answerlife.skill_tools import answer_book, calm, letters

MODULES = (answer_book, calm, letters)
