# skills/AGENTS.md

本文件是 `skills/` 目录的维护入口。
这里不定义产品正式规则，只定义本仓库本地 skills 的边界和使用定位。
仓库级目标与目录路由以根 `../AGENTS.md` 为准。
涉及 UI 还原、页面规格、发布范围或 docs 契约时，以 `../docs/AGENTS.md` 为准。

---

## 1. 当前 skills 归属

| 路径 | 角色 | 是否作为业务正式依据 |
| --- | --- | --- |
| `skills/anybackup-style-system/**` | 风格与视觉参考能力 | 否 |
| `skills/conversation-rich-content/**` | 富内容与协议渲染辅助能力 | 否 |
| `skills/find-skills/**` | skill 发现与整理辅助 | 否 |
| `skills/product-context/**` | 产品背景参考 | 否 |
| `skills/react-best-practices/**` | React 实现辅助 | 否 |

规则：
1. `skills/**` 只能帮助 AI 更好执行，不得成为产品、版本、页面、协议的最终正式依据。
2. skills 可以引用 docs，但不能绕过 docs 的优先级与页面规格检查要求。

---

## 2. 使用边界

1. `anybackup-style-system` 只能作为视觉参考，不能覆盖页面规格里的量化值。
2. `conversation-rich-content` 只能辅助协议理解，不能替代正式的消息与事件渲染契约。
3. `product-context` 只能补背景，不可直接定义发布范围和页面说法。
4. `react-best-practices` 只能优化实现方式，不能越权改变产品结构或视觉验收标准。

---

## 3. 修改规则

以下情况属于慢车道：

1. 新增本地 skill；
2. 修改 skill 的职责、输入边界或输出边界；
3. 让 skill 开始影响 UI 还原、页面结构或协议说法；
4. 让 skill 引入新的正式规则路径。

发生以上任一情况时：

1. 同步检查根 `../AGENTS.md` 是否需要补路由；
2. 如影响 docs 的对外说法，同步检查 `../docs/AGENTS.md`。

---

## 4. 重点检查

必须重点审视的修改：

1. 把 skill 从“辅助能力”升级成“正式依据”；
2. 新建会影响页面还原判断的 skill；
3. 修改会改变 AI 默认输出行为的全局型 skill。
