package site_test

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/fortystory/easy-look-up/internal/site"
)

// fakeFS 造一个内存里的内容目录，测试不依赖磁盘上的真实内容。
func fakeFS() fstest.MapFS {
	return fstest.MapFS{
		"go/demo.json": &fstest.MapFile{Data: []byte(`{
			"id": "demo",
			"title": "演示分组",
			"entries": [
				{
					"title": "演示条目",
					"description": "这是说明文字",
					"code": "var x = 1\nfmt.Println(x)",
					"lang": "go",
					"notes": "这是一个小坑"
				},
				{
					"title": "另一个条目",
					"description": "另一段说明",
					"code": "y := 2",
					"lang": "go",
					"notes": ""
				}
			]
		}`)},
	}
}

func newRouter(t *testing.T, fsys fstest.MapFS) http.Handler {
	t.Helper()
	r, err := site.New(fsys)
	if err != nil {
		t.Fatalf("New 返回错误: %v", err)
	}
	return r
}

func get(t *testing.T, h http.Handler, path string) *httptest.ResponseRecorder {
	t.Helper()
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
	return w
}

// 类别页列出所有类别，并链到各自的详情页。
func TestIndexPage(t *testing.T) {
	h := newRouter(t, fakeFS())
	w := get(t, h, "/")

	if w.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 %d", w.Code, http.StatusOK)
	}
	body := w.Body.String()
	for _, want := range []string{"Go 语言", `href="/go"`, "1 个分组", "2 条内容"} {
		if !strings.Contains(body, want) {
			t.Errorf("响应体里没有 %q", want)
		}
	}
}

// 详情页要把分组、条目、说明、坑都渲染出来。
func TestDetailPage(t *testing.T) {
	h := newRouter(t, fakeFS())
	w := get(t, h, "/go")

	if w.Code != http.StatusOK {
		t.Fatalf("状态码 = %d, 期望 %d", w.Code, http.StatusOK)
	}

	body := w.Body.String()
	for _, want := range []string{
		"演示分组",                 // 分组标题
		"演示条目",                 // 条目标题
		"这是说明文字",               // 条目说明
		"这是一个小坑",               // 常见坑
		`<pre class="chroma">`, // chroma 高亮后的代码块
		`data-search=`,         // 搜索过滤用的属性
		`data-code=`,           // 复制按钮用的原始代码
		`href="#demo"`,         // 分组锚点
	} {
		if !strings.Contains(body, want) {
			t.Errorf("响应体里没有 %q", want)
		}
	}
}

// 没有代码高亮的话页面就没有 <pre>，等于没做高亮。
func TestDetailPageHighlightsCode(t *testing.T) {
	h := newRouter(t, fakeFS())
	body := get(t, h, "/go").Body.String()

	if !strings.Contains(body, `class="kd"`) {
		t.Error("代码块里没有 chroma 的语法 class，高亮没生效")
	}
	if strings.Contains(body, "&lt;span") {
		t.Error("高亮后的 HTML 被转义了")
	}
}

// 搜索用的属性里要包含标题、说明和坑。
func TestDetailPageSearchText(t *testing.T) {
	h := newRouter(t, fakeFS())
	body := get(t, h, "/go").Body.String()

	if !strings.Contains(body, "演示条目 这是说明文字 这是一个小坑") {
		t.Error("data-search 里没有包含标题、说明和坑")
	}
}

// 主题切换按钮和样式表要在页面上。
func TestDetailPageHasThemeToggle(t *testing.T) {
	h := newRouter(t, fakeFS())
	body := get(t, h, "/go").Body.String()

	for _, want := range []string{"theme-toggle", "/static/style.css", "/static/app.js"} {
		if !strings.Contains(body, want) {
			t.Errorf("响应体里没有 %q", want)
		}
	}
}

// 静态资源要能访问，样式表和脚本都在。
func TestStaticFiles(t *testing.T) {
	h := newRouter(t, fakeFS())

	cases := []struct {
		path        string
		contentType string
	}{
		{path: "/static/style.css", contentType: "text/css"},
		{path: "/static/app.js", contentType: "javascript"},
	}
	for _, c := range cases {
		t.Run(c.path, func(t *testing.T) {
			w := get(t, h, c.path)
			if w.Code != http.StatusOK {
				t.Fatalf("状态码 = %d, 期望 %d", w.Code, http.StatusOK)
			}
			if !strings.Contains(w.Header().Get("Content-Type"), c.contentType) {
				t.Errorf("Content-Type = %q, 期望包含 %q", w.Header().Get("Content-Type"), c.contentType)
			}
			if w.Body.Len() == 0 {
				t.Error("响应体是空的")
			}
		})
	}
}

// 样式表里要有亮色和暗色两套变量。
func TestStyleSheetHasBothThemes(t *testing.T) {
	h := newRouter(t, fakeFS())
	body := get(t, h, "/static/style.css").Body.String()

	for _, want := range []string{":root", `[data-theme="dark"]`, "prefers-color-scheme"} {
		if !strings.Contains(body, want) {
			t.Errorf("样式表里没有 %q", want)
		}
	}
}

// 不存在的类别返回 404。
func TestUnknownCategory(t *testing.T) {
	h := newRouter(t, fakeFS())
	w := get(t, h, "/nope")
	if w.Code != http.StatusNotFound {
		t.Errorf("状态码 = %d, 期望 %d", w.Code, http.StatusNotFound)
	}
}

// 内容坏掉时 New 要报错，而不是返回一个坏掉的站点。
func TestNewWithBadContent(t *testing.T) {
	fsys := fstest.MapFS{
		"go/broken.json": &fstest.MapFile{Data: []byte(`{"id": "broken", "title":`)},
	}
	if _, err := site.New(fsys); err == nil {
		t.Fatal("坏内容应该返回错误，却返回了 nil")
	}
}

func TestNewWithEmptyContent(t *testing.T) {
	if _, err := site.New(fstest.MapFS{}); err == nil {
		t.Fatal("空内容目录应该返回错误，却返回了 nil")
	}
}

// 详情页有几百 KB 的高亮 HTML，带 Accept-Encoding 时要压缩。
func TestDetailPageIsCompressed(t *testing.T) {
	h := newRouter(t, fakeFS())

	w := httptest.NewRecorder()
	req := httptest.NewRequest("GET", "/go", nil)
	req.Header.Set("Accept-Encoding", "gzip")
	h.ServeHTTP(w, req)

	if w.Header().Get("Content-Encoding") != "gzip" {
		t.Errorf("Content-Encoding = %q, 期望 %q", w.Header().Get("Content-Encoding"), "gzip")
	}
}
