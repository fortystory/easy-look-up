package site

import (
	"bytes"
	"embed"
	"fmt"
	"html/template"
	"io/fs"
	"net/http"
	"strings"

	"github.com/alecthomas/chroma/v2/formatters/html"
	"github.com/alecthomas/chroma/v2/lexers"
	"github.com/alecthomas/chroma/v2/styles"

	"github.com/gin-gonic/gin"

	"github.com/fortystory/easy-look-up/internal/content"
)

// 模板和静态资源随二进制一起发布。
//
//go:embed templates/*.html
var templatesFS embed.FS

//go:embed static
var staticFS embed.FS

type entryView struct {
	Title       string
	Description string
	Code        template.HTML
	RawCode     string
	Notes       string
	SearchText  string
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

type categoryMeta struct {
	ID         string
	Title      string
	GroupCount int
	EntryCount int
}

type indexView struct {
	Categories []categoryMeta
}

// New 加载所有类别的内容，返回配好路由的 Gin 实例。
// 内容加载失败时返回 error。
func New(fsys fs.FS) (*gin.Engine, error) {
	ids, err := content.List(fsys)
	if err != nil {
		return nil, err
	}
	if len(ids) == 0 {
		return nil, fmt.Errorf("内容目录里没有任何类别")
	}

	categories := make(map[string]content.Category, len(ids))
	meta := make([]categoryMeta, 0, len(ids))

	for _, id := range ids {
		category, err := content.Load(fsys, id)
		if err != nil {
			return nil, err
		}
		categories[id] = category
		meta = append(meta, categoryMeta{
			ID:         category.ID,
			Title:      category.Title,
			GroupCount: len(category.Groups),
			EntryCount: entryCount(category),
		})
	}

	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())

	tmpl, err := template.ParseFS(templatesFS, "templates/*.html")
	if err != nil {
		return nil, fmt.Errorf("解析模板: %w", err)
	}
	r.SetHTMLTemplate(tmpl)

	static, err := fs.Sub(staticFS, "static")
	if err != nil {
		return nil, fmt.Errorf("准备静态资源: %w", err)
	}
	r.StaticFS("/static", http.FS(static))

	r.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", indexView{Categories: meta})
	})

	// 每个类别注册一条固定路由。内容是编译进二进制的，类别集合启动时已知，
	// 所以没必要用 /:category 通配——那样还会和 /static/*filepath 抢路由。
	for _, id := range ids {
		category := categories[id]
		r.GET("/"+id, func(c *gin.Context) {
			view, err := toView(category)
			if err != nil {
				c.String(http.StatusInternalServerError, "渲染失败: %v", err)
				return
			}
			c.HTML(http.StatusOK, "detail.html", view)
		})
	}

	return r, nil
}

// entryCount 统计一个类别里的条目总数。
func entryCount(category content.Category) int {
	n := 0
	for _, group := range category.Groups {
		n += len(group.Entries)
	}
	return n
}

// toView 把内容结构转成模板用的视图模型。
func toView(category content.Category) (detailView, error) {
	view := detailView{Title: category.Title}

	for _, group := range category.Groups {
		gv := groupView{ID: group.ID, Title: group.Title}
		for _, entry := range group.Entries {
			code, err := highlight(entry.Code, entry.Lang)
			if err != nil {
				return detailView{}, fmt.Errorf("高亮 %s/%s 的代码: %w", group.ID, entry.Title, err)
			}
			gv.Entries = append(gv.Entries, entryView{
				Title:       entry.Title,
				Description: entry.Description,
				Code:        code,
				RawCode:     entry.Code,
				Notes:       entry.Notes,
				SearchText:  strings.Join([]string{entry.Title, entry.Description, entry.Notes}, " "),
			})
		}
		view.Groups = append(view.Groups, gv)
	}
	return view, nil
}

// highlight 用 chroma 把代码高亮成 HTML。
//
// 用 class 模式而不是内联样式：内联样式把颜色写死在 HTML 里，
// 暗色主题就没法接管了。class 模式由 style.css 按主题给 .chroma .kd 等上色。
func highlight(code string, lang string) (template.HTML, error) {
	lexer := lexers.Get(lang)
	if lexer == nil {
		return "", fmt.Errorf("unknown lexer: %s", lang)
	}
	style := styles.Get("github")
	formatter := html.New(html.WithClasses(true), html.TabWidth(4))

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
