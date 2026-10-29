# easy-look-up

快速查找 —— 一个只读的代码速查网站。按「类别 → 分组 → 条目」组织内容，每条内容是一段带语法高亮、可一键复制的代码。

用来查 Go 语言语法、Go 标准库和 Gin 框架的用法。

## 跑起来

```bash
go mod download      # 第一次要拉依赖
go run .
```

浏览器打开 <http://localhost:8080>。

- `/` —— 类别页
- `/go` —— Go 语言
- `/stdlib` —— Go 标准库
- `/gin` —— Gin 框架
- `/interview-go` —— Go 语言与运行时面试题
- `/interview-concurrency` —— 并发与高并发面试题
- `/interview-gin` —— Gin 面试题
- `/interview-mysql` —— MySQL 面试题
- `/interview-redis` —— Redis 面试题
- `/interview-web` —— Web 与 HTTP 面试题
- `/interview-network` —— 网络与 TCP/IP 面试题

## 跑测试

```bash
go test ./...
```

## 目录结构

```
.
├── main.go                     入口：embed 内容目录、启动服务
├── content/                    内容（JSON，按类别分目录）
│   ├── go/                     Go 语言
│   ├── stdlib/                 Go 标准库
│   ├── gin/                    Gin 框架
│   └── interview-*/            面试题（问答型条目）
├── internal/
│   ├── content/                加载并解析内容
│   └── site/                   路由、模板渲染、静态资源
│       ├── templates/          HTML 模板
│       └── static/             样式表和脚本
├── scripts/
│   └── verify_content.py       内容校验工具
└── docs/
    ├── content-guide.md        内容编写规范
    └── agents/                 agent 工作约定
```

- **内容包**只管把 JSON 变成结构体，不认识 HTTP
- **站点包**只管把结构体变成 HTML，不认识文件格式
- 两者之间的边界是 `content.Category`

内容、模板和静态资源都通过 `go:embed` 编译进二进制，部署只需要一个可执行文件。

## 怎么加一条内容

内容放在 `content/<类别>/<分组>.json`，一个分组一个文件。字段格式和写作要求见 [docs/content-guide.md](docs/content-guide.md)。

内容有两种形态：**代码片段型**（有 `code`，讲「某个语法怎么写」）和**问答型**（有 `answer` 数组，讲「面试常问的某个问题」）。面试题的标题写成问句，答案拆成 3–6 个要点。

### 1. 建文件

文件名要和分组里的 `id` 一致。比如加一个分组 `content/go/context.json`：

```json
{
  "id": "context",
  "title": "上下文",
  "entries": [
    {
      "title": "取消一个上下文",
      "description": "context 用来取消耗时操作，父 context 取消时子 context 也取消。",
      "code": "ctx, cancel := context.WithTimeout(context.Background(), time.Second)\ndefer cancel()",
      "lang": "go",
      "notes": "忘了 defer cancel() 会泄漏，定时器到点才释放。"
    }
  ]
}
```

### 2. 校验

```bash
python3 scripts/verify_content.py
```

它会把每条代码片段交给 Go 编译器**实际编译一遍**，组合示例还会跑起来。编译不过就说明代码写错了。

标了 `"expect_error": true` 的条目反过来——必须编译失败（这类条目的教学点就是那个报错）。

### 3. 加新类别

新建 `content/<类别名>/` 目录，放至少一个 JSON 文件就行。路由和数据模型不用改。

类别的显示名在 `internal/content/content.go` 的 `displayNames` 里登记；没登记的会用目录名首字母大写兜底。

## 页面能做什么

- **搜索过滤**：详情页顶部的输入框实时过滤条目，匹配标题、说明和常见坑，不匹配代码正文。没有匹配内容的分组自动隐藏
- **复制代码**：每个代码块右上角的按钮，一键复制原文
- **亮色/暗色**：右上角切换。没手动选过时跟随系统偏好，手动选过就记住选择
- **锚点导航**：详情页顶部列出所有分组，点一下跳过去

## 一些实现上的选择

- **语法高亮在服务端**：chroma 生成 HTML，浏览器不加载高亮库
- **chroma 用 class 模式**：颜色写在样式表里而不是内联样式，暗色主题才能接管
- **过滤在浏览器端**：条目本来就要整页下发，没有额外成本
- **搜索字段用 `data-search` 属性**：不重复内嵌一份 JSON

## 约定

代码之外的内容（文档、注释）尽量用中文；代码标识符、命令、路径保持原文。详见 [AGENTS.md](AGENTS.md)。

领域术语见 [GLOSSARY.md](GLOSSARY.md)。
