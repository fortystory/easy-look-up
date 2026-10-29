package content_test

import (
	"os"
	"strings"
	"testing"
	"testing/fstest"

	"github.com/fortystory/easy-look-up/internal/content"
)

func TestList(t *testing.T) {
	ids, err := content.List(os.DirFS("../../content"))
	if err != nil {
		t.Fatalf("List 返回错误: %v", err)
	}
	if len(ids) == 0 {
		t.Fatal("List 返回了空列表，仓库里应该有类别")
	}
	for i, id := range ids {
		if id == "" {
			t.Errorf("第 %d 个类别 id 是空字符串", i)
		}
		if i > 0 && ids[i-1] > id {
			t.Errorf("List 返回的 id 没有按字典序排列: %q 出现在 %q 之后", ids[i-1], id)
		}
	}
}

func TestListEmpty(t *testing.T) {
	ids, err := content.List(fstest.MapFS{})
	if err != nil {
		t.Fatalf("List 返回错误: %v", err)
	}
	if len(ids) != 0 {
		t.Errorf("空目录应该返回空列表，却返回了 %v", ids)
	}
}

func TestLoad(t *testing.T) {
	c, err := content.Load(os.DirFS("../../content"), "go")
	if err != nil {
		t.Fatalf("Load 返回错误: %v", err)
	}
	if c.ID != "go" {
		t.Errorf("类别 id = %q, 期望 %q", c.ID, "go")
	}
	if c.Title == "" {
		t.Error("类别标题是空的")
	}
	if len(c.Groups) == 0 {
		t.Fatal("Go 类别下没有任何分组")
	}
	if c.Groups[0].Title != "基本类型与变量" {
		t.Errorf("第一个分组标题 = %q, 期望 %q", c.Groups[0].Title, "基本类型与变量")
	}
	if c.Groups[0].ID != "basic-types" {
		t.Errorf("第一个分组 id = %q, 期望 %q", c.Groups[0].ID, "basic-types")
	}
	if len(c.Groups[0].Entries) == 0 {
		t.Fatal("第一个分组下没有任何条目")
	}
	first := c.Groups[0].Entries[0]
	if first.Title != "整型" {
		t.Errorf("第一条条目标题 = %q, 期望 %q", first.Title, "整型")
	}
	if first.Description == "" {
		t.Error("第一条条目没有说明")
	}
	if first.Code == "" {
		t.Error("第一条条目没有代码")
	}
	if first.Lang != "go" {
		t.Errorf("第一条条目的 lang = %q, 期望 %q", first.Lang, "go")
	}
}

// 坏 JSON 必须报错，而且错误信息里要指出是哪个文件坏了。
func TestLoadBadJSON(t *testing.T) {
	fsys := fstest.MapFS{
		"go/broken.json": &fstest.MapFile{Data: []byte(`{"id": "broken", "title":`)},
	}
	_, err := content.Load(fsys, "go")
	if err == nil {
		t.Fatal("坏 JSON 应该返回错误，却返回了 nil")
	}
	if !strings.Contains(err.Error(), "broken.json") {
		t.Errorf("错误信息 = %q, 期望包含文件名 %q", err.Error(), "broken.json")
	}
}

// 类别目录不存在也要报错。
func TestLoadMissingCategory(t *testing.T) {
	_, err := content.Load(fstest.MapFS{}, "nope")
	if err == nil {
		t.Fatal("不存在的类别应该返回错误，却返回了 nil")
	}
}

// 目录存在但没有 JSON 文件也要报错。
func TestLoadEmptyCategory(t *testing.T) {
	fsys := fstest.MapFS{
		"go/readme.txt": &fstest.MapFile{Data: []byte("不是内容")},
	}
	_, err := content.Load(fsys, "go")
	if err == nil {
		t.Fatal("没有分组文件的类别应该返回错误，却返回了 nil")
	}
}

// 缺字段要报错，并且错误信息里带文件名。
func TestLoadMissingField(t *testing.T) {
	cases := []struct {
		name string
		data string
	}{
		{name: "缺分组标题", data: `{"id": "g", "entries": []}`},
		{name: "缺条目标题", data: `{"id": "g", "title": "G", "entries": [{"code": "x := 1"}]}`},
		{name: "缺条目代码", data: `{"id": "g", "title": "G", "entries": [{"title": "T"}]}`},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			fsys := fstest.MapFS{
				"go/invalid.json": &fstest.MapFile{Data: []byte(c.data)},
			}
			_, err := content.Load(fsys, "go")
			if err == nil {
				t.Fatal("缺字段应该返回错误，却返回了 nil")
			}
			if !strings.Contains(err.Error(), "invalid.json") {
				t.Errorf("错误信息 = %q, 期望包含文件名 %q", err.Error(), "invalid.json")
			}
		})
	}
}

// 非 JSON 文件要被跳过，不能当成内容读。
func TestLoadSkipsNonJSON(t *testing.T) {
	fsys := fstest.MapFS{
		"go/notes.txt": &fstest.MapFile{Data: []byte("随便什么")},
		"go/real.json": &fstest.MapFile{Data: []byte(`{"id": "real", "title": "真分组", "entries": [{"title": "T", "description": "D", "code": "x := 1", "lang": "go"}]}`)},
	}
	c, err := content.Load(fsys, "go")
	if err != nil {
		t.Fatalf("Load 返回错误: %v", err)
	}
	if len(c.Groups) != 1 {
		t.Fatalf("分组数量 = %d, 期望 1", len(c.Groups))
	}
	if c.Groups[0].Title != "真分组" {
		t.Errorf("分组标题 = %q, 期望 %q", c.Groups[0].Title, "真分组")
	}
}
