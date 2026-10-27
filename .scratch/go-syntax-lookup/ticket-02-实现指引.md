# Ticket 02 实现指引：详情页最小链路

这份文档只给**契约**，不给实现。数据结构、函数签名、路由路径、测试断言都定死，函数体你自己写。

对应 ticket：[02 详情页最小链路](issues/02-detail-page-minimal-slice.md)

---

## 1. 做完了长什么样

`go run .` 之后打开 `http://localhost:8080/go`，页面应该：

- 大标题是「基本类型与变量」
- 下面 15 条条目，每条有标题、一到两句说明、一段**带语法高亮**的代码块
- 代码里 `var` 是红色、`string` 是蓝色（github 主题配色）
- 页面里有 `<pre>` 标签（这是「确实做了高亮」的证据，不是原样输出代码）

## 2. 要创建的文件

```
main.go                        新建，package main
go.mod                         新建
internal/content/content.go    新建，内容加载与解析
internal/content/content_test.go
internal/site/site.go          新建，路由与 handler
internal/site/site_test.go
templates/detail.html          新建，详情页模板
content/go/basic-types.json    已存在（ticket 01 产出）
```

`static/style.css` 这片不用管，ticket 09 再做。现在页面没样式是正常的。

## 3. 依赖与初始化

```bash
go mod init github.com/fortystory/easy-look-up
go get github.com/gin-gonic/gin@v1.12.0
go get github.com/alecthomas/chroma/v2@v2.23.1
```

## 4. 内容包的契约

`internal/content/content.go`，package content：

### 数据结构

字段名必须和 JSON 里的键一一对应：

```go
type Entry struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Code        string `json:"code"`
	Lang        string `json:"lang"`
	Notes       string `json:"notes"`
}

type Group struct {
	ID      string  `json:"id"`
	Title   string  `json:"title"`
	Entries []Entry `json:"entries"`
}

type Category struct {
	ID     string
	Title  string
	Groups []Group
}
```

### 函数

```go
// Load 读取 fsys 里某个类别目录下的全部分组文件。
// 解析失败返回 error，error 的信息里必须包含出错的文件名。
func Load(fsys fs.FS, categoryID string) (Category, error)
```

- `fsys` 是根在「内容目录」的文件系统，里面有 `go/basic-types.json` 这样的路径
- `categoryID` 是类别目录名，目前只有 `"go"`
- 类别的显示名 `Category.Title` 由目录名推导（`"go"` → `"Go"`）。这是最简单的做法，ticket 03 做类别页时可能需要调整
- 分组按文件名排序（`fs.ReadDir` 返回的就是排序好的），保持内容作者在文件里定的顺序

### 错误要覆盖的情况

| 情况 | 期望行为 |
|---|---|
| 类别目录不存在 | 返回 error |
| 目录里没有 JSON 文件 | 返回 error |
| JSON 语法错 | 返回 error，信息含文件名 |
| 条目缺 `title` 或 `code` | 返回 error，信息含文件名（**ticket 08 会正式要求，现在顺手做了不亏**） |

Go 的 `json.Unmarshal` 对缺失字段不报错，所以「缺字段」要自己检查。参考做法：反序列化后遍历每个 entry，`Title == "" || Code == ""` 就返回带文件名的 error。

## 5. 站点包的契约

`internal/site/site.go`，package site：

```go
// New 加载内容并返回配好路由的 Gin 实例。
// 内容加载失败时返回 error。
func New(fsys fs.FS, categoryID string) (*gin.Engine, error)
```

### 路由

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/go` | 渲染详情页 |

路径由 categoryID 拼出来（`"/" + categoryID`），这样加新类别不用改代码。**这条路由是本片唯一必需的**，404 留给 ticket 08。

### 模板

用 Gin 自带的模板引擎，它底层就是 `html/template`：

```go
r.LoadHTMLGlob("templates/*.html")
```

模板文件叫 `detail.html`，渲染时用这个名字。模板从**磁盘**读（不是 embed）——这是刻意的简化，`go run .` 在仓库根目录跑就行。模板以后要不要也 embed 进二进制，留给 ticket 11 的重构轮。

### 视图模型

chroma 输出的 HTML 里有 `<span>` 和 `style` 属性，直接塞进模板会被 `html/template` 转义成可见文本。所以要转成 `template.HTML`：

```go
type entryView struct {
	Title       string
	Description string
	Code        template.HTML
	Notes       string
}

type groupView struct {
	ID      string
	Title   string
	Entries []entryView
}

type detailView struct {
	Title  string
	Groups []groupView
}
```

handler 里把 `content.Category` 转成 `detailView` 再交给 `c.HTML(200, "detail.html", view)`。

## 6. chroma 的正确用法

**这段是照抄就能跑的**，别自己摸索 API：

```go
import (
	"bytes"

	"github.com/alecthomas/chroma/v2/formatters/html"
	"github.com/alecthomas/chroma/v2/lexers"
	"github.com/alecthomas/chroma/v2/styles"
)

func highlight(code string, lang string) (template.HTML, error) {
	lexer := lexers.Get(lang)
	if lexer == nil {
		return "", fmt.Errorf("unknown lexer: %s", lang)
	}
	style := styles.Get("github")
	formatter := html.New(html.WithClasses(false), html.TabWidth(4))

	iterator, err := lexer.Tokenise(nil, code)
	if err != nil {
		return "", err
	}
	var buf bytes.Buffer
	if err := formatter.Format(&buf, style, iterator); err != nil {
		return "", err
	}
	return template.HTML(buf.String()), nil
}
```

### 两个陷阱

1. **别用 `formatters.Get("html")`**。它注册的是 `html.New(html.Standalone(true), html.WithClasses(true))`——会生成一整个 `<html><body>` 文档，而且用 class 而不是内联样式，你还得额外引 chroma 的 CSS 文件。要嵌进自己的页面，必须用 `formatters/html` 包里的 `html.New(...)`（像上面那样）。
2. **`lexers.Get` 找不到 lexer 时返回 nil，不报错**。上面已经处理了。

验证过的输出长这样（内联样式，只要一个 `<pre>` 片段）：

```html
<pre style="background-color:#f7f7f7;..."><code><span style="display:flex;"><span><span style="color:#cf222e">var</span>...
```

## 7. 入口包的契约

`main.go`，package main：

```go
//go:embed content
var contentFS embed.FS

func main() {
	fsys, err := fs.Sub(contentFS, "content")
	if err != nil {
		log.Fatal(err)
	}
	r, err := site.New(fsys, "go")
	if err != nil {
		log.Fatal(err)
	}
	r.Run(":8080")
}
```

### 陷阱：embed 必须在根包

`//go:embed` 只能嵌入**当前包目录及其子目录**里的文件，不能指向上级目录。内容目录 `content/` 在仓库根，而根目录的包是 `package main`——所以 embed 指令只能写在 `main.go` 里，`internal/content` 碰不到它。

这也是为什么 `site.New` 收的是 `fs.FS` 而不是 `embed.FS`：embed 在 main 里做，`fs.Sub` 之后作为参数传下去。这样 `internal/content` 和 `internal/site` 的测试都能用 `fstest.MapFS` 在内存里造文件系统，不碰磁盘。

`//go:embed content` 嵌入后的路径是 `content/go/basic-types.json`，所以要用 `fs.Sub(contentFS, "content")` 剥掉前缀，`content.Load` 拿到的路径才是 `go/basic-types.json`。

## 8. 两个测试 seam

### 内容层：`internal/content/content_test.go`

用**真实内容文件**测「合法内容」：

```go
fsys := os.DirFS("../../content")
c, err := content.Load(fsys, "go")
```

断言：分组数量、分组标题是「基本类型与变量」、条目数量是 15、第一条的标题是「整型」。

用**内存文件系统**测「非法内容」，`testing/fstest`：

```go
fsys := fstest.MapFS{
	"go/broken.json": &fstest.MapFile{Data: []byte(`{"id": "broken", "title":`)}, // 故意截断
}
```

断言：`Load` 返回 error，且 `err.Error()` 里含 `broken.json`。

（`testing/fstest` 是标准库，`go doc testing/fstest` 有说明。）

### HTTP 层：`internal/site/site_test.go`

用 `httptest`：

```go
r, err := site.New(fsys, "go")
w := httptest.NewRecorder()
req := httptest.NewRequest("GET", "/go", nil)
r.ServeHTTP(w, req)
```

`fsys` 用 `fstest.MapFS` 造一个小的假类别（一个分组一条目就够了），这样测试不依赖真实内容文件，跑得快。

断言三件事：

1. `w.Code == 200`
2. `w.Body.String()` 含分组标题
3. `w.Body.String()` 含 `<pre` —— 这条是在断言「chroma 高亮真的生效了」，因为原样输出代码不会有 `<pre>`

## 9. 跑起来

```bash
go test ./...
go run .
# 浏览器打开 http://localhost:8080/go
```

## 10. 提交

分支 `feat/02-detail-page` 上，分开提交：

```
test: 给内容加载和详情页加测试
feat: 实现详情页最小链路
```

先写测试再写实现（这是我们说好的 TDD）。

---

## 附：Go 里你可能会绊到的几个点

- `html/template` 会对内容转义。`template.HTML` 是「这段已经安全，别转义」的标记，只能给自己生成的内容用
- `fs.ReadDir` 返回的 `[]fs.DirEntry` 是按文件名排序的
- `json.Unmarshal` 忽略未知字段、也不报缺失字段
- Gin 的 `c.HTML` 要先 `LoadHTMLGlob`，否则模板找不到会 panic
- 测试里别用 `http.Get` 真的发请求，用 `httptest.NewRecorder()`
