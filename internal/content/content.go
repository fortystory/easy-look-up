package content

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"path"
	"strings"
)

type Entry struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Code        string `json:"code"`
	Lang        string `json:"lang"`
	Notes       string `json:"notes"`
	// Answer 是问答类条目的答案要点。代码片段类条目不用这个字段。
	Answer []string `json:"answer"`
	// ExpectError 为 true 表示这段代码是故意编译不过的，教学点就是那个报错。
	// 页面上要标出来，否则用户会以为内容写错了。
	ExpectError bool `json:"expect_error"`
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

// List 列出内容目录下的所有类别 id，按字典序。
// 一个目录下只要有 .json 文件就算一个类别。
func List(fsys fs.FS) ([]string, error) {
	entries, err := fs.ReadDir(fsys, ".")
	if err != nil {
		return nil, fmt.Errorf("读取内容目录: %w", err)
	}

	var ids []string
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		files, err := fs.ReadDir(fsys, entry.Name())
		if err != nil {
			return nil, fmt.Errorf("读取类别目录 %q: %w", entry.Name(), err)
		}
		for _, file := range files {
			if !file.IsDir() && strings.HasSuffix(file.Name(), ".json") {
				ids = append(ids, entry.Name())
				break
			}
		}
	}
	return ids, nil
}

// Load 读取 fsys 里某个类别目录下的全部分组文件。
// 解析失败返回 error，error 的信息里必须包含出错的文件名。
func Load(fsys fs.FS, categoryID string) (Category, error) {

	category := Category{
		ID:    categoryID,
		Title: displayTitle(categoryID),
	}

	entries, err := fs.ReadDir(fsys, categoryID)
	if err != nil {
		return Category{}, fmt.Errorf("读取类别目录 %q: %w", categoryID, err)
	}

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		name := entry.Name()
		full := path.Join(categoryID, name)

		group, err := loadGroup(fsys, full)
		if err != nil {
			return Category{}, err
		}
		category.Groups = append(category.Groups, group)
	}

	if len(category.Groups) == 0 {
		return Category{}, fmt.Errorf("类别 %q 下没有任何分组文件", categoryID)
	}
	return category, nil
}

func loadGroup(fsys fs.FS, name string) (Group, error) {
	data, err := fs.ReadFile(fsys, name)
	if err != nil {
		return Group{}, fmt.Errorf("读取 %s: %w", name, err)
	}

	var group Group
	if err := json.Unmarshal(data, &group); err != nil {
		return Group{}, fmt.Errorf("解析 %s: %w", name, err)
	}

	if group.Title == "" {
		return Group{}, fmt.Errorf("解析 %s: 缺少 title 字段", name)
	}

	for i, entry := range group.Entries {
		if entry.Title == "" {
			return Group{}, fmt.Errorf("解析 %s: 第 %d 个条目缺少 title", name, i+1)
		}
		// 代码片段类条目必须有 code；问答类条目用 answer，可以没有 code
		if entry.Code == "" && len(entry.Answer) == 0 {
			return Group{}, fmt.Errorf("解析 %s: 第 %d 个条目既没有 code 也没有 answer", name, i+1)
		}
	}

	return group, nil

}

// displayNames 是已知类别的显示名。
var displayNames = map[string]string{
	"go":                    "Go 语言",
	"stdlib":                "Go 标准库",
	"gin":                   "Gin 框架",
	"interview-go":          "Go 面试题",
	"interview-concurrency": "并发与高并发面试题",
	"interview-gin":         "Gin 面试题",
	"interview-mysql":       "MySQL 面试题",
	"interview-redis":       "Redis 面试题",
	"interview-web":         "Web 面试题",
	"interview-network":     "网络面试题",
}

// displayTitle 从类别 id 推导显示名："go" → "Go 语言"。
func displayTitle(categoryID string) string {
	if name, ok := displayNames[categoryID]; ok {
		return name
	}
	if categoryID == "" {
		return ""
	}
	return strings.ToUpper(categoryID[:1]) + categoryID[1:]
}
