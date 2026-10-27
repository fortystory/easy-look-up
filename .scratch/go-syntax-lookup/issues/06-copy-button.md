Category: enhancement
Status: ready-for-agent

# 06: 复制按钮

**What to build:**

每条代码旁边一个复制按钮，点一下整段代码进剪贴板。这是速查站的最后一块拼图——查到了就得能拿走。

**Blocked by:** 02 详情页最小链路

- [ ] 每个代码块有一个复制按钮
- [ ] 点击后代码全文进入剪贴板
- [ ] 使用 `navigator.clipboard.writeText`，在它不可用时有 `execCommand` 兜底
- [ ] 复制成功有可见反馈（按钮文案变化或提示），失败也有反馈
- [ ] 代码块里的换行和缩进被原样保留，复制出来的代码能直接粘贴进编辑器运行
