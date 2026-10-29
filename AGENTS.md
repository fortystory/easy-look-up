## 语言约定

代码之外的内容尽量使用中文：文档、注释、issue 与 spec 正文。

代码标识符、命令、路径、包名、API 名称、skill 名、triage label 字符串等保持原文，不翻译。

## 内容规范

内容以 JSON 存放于 `content/<类别>/<分组>.json`，一个分组一个文件。字段格式和写作要求见 `docs/content-guide.md`。

改完内容必须跑校验：

```bash
python3 scripts/verify_content.py
```

它会把每条代码片段交给 Go 编译器实际编译一遍，组合示例还会跑起来。标了 `expect_error` 的条目反过来——必须编译失败。

## Agent skills

### Issue tracker

Issues 和 specs 以 markdown 文件存放于 `.scratch/<feature-slug>/`。见 `docs/agents/issue-tracker.md`。

### Triage labels

五个 canonical triage roles，label 字符串与 role 名相同。见 `docs/agents/triage-labels.md`。

### Domain docs

Single-context：根目录 `GLOSSARY.md` + `docs/adr/`。见 `docs/agents/domain.md`。
