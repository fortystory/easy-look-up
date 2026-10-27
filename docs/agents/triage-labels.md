# Triage 标签

Skills 使用五个 canonical triage roles。这个文件把这些 roles 映射到此 repo issue tracker 中实际使用的 label 字符串。

| mattpocock/skills 中的 label | 我们 tracker 中的 label | 含义                              |
| ---------------------------- | ----------------------- | --------------------------------- |
| `needs-triage`               | `needs-triage`          | maintainer 需要评估这个 issue     |
| `needs-info`                 | `needs-info`            | 等待 reporter 补充更多信息        |
| `ready-for-agent`            | `ready-for-agent`       | 说明完整，可以交给 AFK agent 接手 |
| `ready-for-human`            | `ready-for-human`       | 需要人工实现                      |
| `wontfix`                    | `wontfix`               | 不会处理                          |

当某个 skill 提到 role（例如 "apply the AFK-ready triage label"）时，使用此表中对应的 label 字符串。

## Label 在本地 tracker 中的存储位置

本 repo 的 tracker 是本地 markdown（见 `issue-tracker.md`），没有 GitHub 那样的 label 机制。role 以 issue 文件顶部附近的一行记录：

```markdown
Status: needs-triage
```

改状态就是改这一行的值。文件的 `Status:` 与 `triage-labels.md` 表格右列一一对应。

## Category roles

每个已 triage 的 issue 应当恰好携带**一个** category role 和**一个** state role。category 记录在同一位置附近的 `Category:` 行：

| 分类 role     | 含义         |
| ------------- | ------------ |
| `bug`         | 某个东西坏了 |
| `enhancement` | 新功能或改进 |

```markdown
Category: bug
Status: needs-triage
```

注意 `Category:`（triage 分类：`bug`/`enhancement`）与 wayfinding 的 `Type:`（ticket 类型：`research`/`prototype`/`grilling`/`task`）是两套不同的行，不要混用。
