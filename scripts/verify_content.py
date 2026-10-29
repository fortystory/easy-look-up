#!/usr/bin/env python3
"""校验 content/ 下的所有内容文件。

对每个分组文件：
  - 校验 JSON 合法、字段齐全
  - 把每条代码片段包成可编译单元，交给 Go 编译器
  - 标了 "expect_error": true 的条目必须编译失败（这类条目的教学点就是编译报错）
  - 完整程序（以 package main 开头）额外跑一遍
  - 检查 gofmt 规范

用法：
  python3 scripts/verify_content.py            # 校验全部类别
  python3 scripts/verify_content.py go         # 只校验某个类别
  python3 scripts/verify_content.py go stdlib  # 校验多个类别
"""

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(ROOT, "content")
# 临时目录按进程隔离：多个校验同时跑时不会互相覆盖 main.go
TMP = os.path.join(ROOT, ".verify_tmp-%d" % os.getpid())

REQUIRED_ENTRY_FIELDS = ("title", "description", "code", "lang")
REQUIRED_GROUP_FIELDS = ("id", "title", "entries")

# 顶层 func 声明。函数体内不允许嵌套 func（方法和具名函数都不行），
# 所以含它们的片段要放到包级。type 声明在函数体内是合法的，不受影响。
TOP_LEVEL_FUNC = re.compile(r"^func\s", re.M)
HAS_MAIN = re.compile(r"^func main\(", re.M)

# 片段里可能用到的标准库包：包名 → 导入路径。
# 只在代码里真的出现 `pkg.` 时才加进 import，否则会报 unused import。
STDLIB = {
    "bufio": "bufio",
    "bytes": "bytes",
    "cmp": "cmp",
    "context": "context",
    "errors": "errors",
    "fmt": "fmt",
    "io": "io",
    "json": "encoding/json",
    "log": "log",
    "maps": "maps",
    "math": "math",
    "os": "os",
    "path": "path",
    "filepath": "path/filepath",
    "reflect": "reflect",
    "regexp": "regexp",
    "slices": "slices",
    "sort": "sort",
    "strconv": "strconv",
    "strings": "strings",
    "sync": "sync",
    "time": "time",
    "unicode": "unicode",
}

COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def used_packages(code):
    """找出代码里用到的标准库包。注释里的不算。"""
    body = COMMENT.sub("", code)
    names = set()
    for name in STDLIB:
        if re.search(r"\b" + re.escape(name) + r"\s*\.", body):
            names.add(name)
    return sorted(names)


def import_block(names):
    """生成 import 语句块。fmt 永远在。"""
    others = [STDLIB[n] for n in names if n != "fmt"]
    if not others:
        return 'import "fmt"'
    lines = ['\t"fmt"'] + ['\t"%s"' % p for p in sorted(others)]
    return "import (\n" + "\n".join(lines) + "\n)"


def wrap(code):
    """把代码片段包进 func main()，返回包装后的源码。"""
    imports = import_block(used_packages(code))
    return (
        "package main\n\n"
        + imports
        + "\n\nvar _ = fmt.Println\n\nfunc main() {\n"
        + code
        + "\n}\n"
    )


def wrap_package_level(code):
    """把代码片段放包级，返回包装后的源码。

    用于含顶层 func 声明的片段——那种声明不能写在函数体内。
    """
    imports = import_block(used_packages(code))
    tail = "" if HAS_MAIN.search(code) else "\nfunc main() {}\n"
    return (
        "package main\n\n"
        + imports
        + "\n\nvar _ = fmt.Println\n\n"
        + code
        + tail
    )


def variants(code):
    """给出所有可能的包装方式，按优先级排列。

    片段以 package main 开头说明它本身就是完整程序，原样使用。
    """
    if code.lstrip().startswith("package main"):
        return [code]
    out = [wrap(code)]
    if TOP_LEVEL_FUNC.search(code):
        out.append(wrap_package_level(code))
    return out


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def body_of(src):
    """取出 func main() 的函数体，逐行去掉缩进。"""
    lines = src.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("func main()")), -1)
    if start < 0:
        return []
    end = len(lines) - 1
    while end > start and lines[end].strip() != "}":
        end -= 1
    return [l.strip() for l in lines[start + 1:end] if l.strip()]


def gofmt_problem(src, tmp):
    """返回 gofmt 的问题描述；没问题返回 None。

    片段被包在 func main() 里，gofmt 会重排缩进，所以逐行去掉缩进再比较。
    """
    path = os.path.join(tmp, "main.go")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)

    out = run(["gofmt", path], tmp)
    if out.returncode != 0:
        return out.stderr.strip()[:200]

    want, got = body_of(src), body_of(out.stdout)
    if want == got:
        return None

    for i, (a, b) in enumerate(zip(want, got)):
        if a != b:
            return "第 %d 行 gofmt 后会变成：%s（当前是 %s）" % (i + 1, b, a)
    return "行数不一致：gofmt 后 %d 行，当前 %d 行" % (len(got), len(want))


def check_entry(entry, tmp):
    """返回 (是否通过, 说明文字, 附加输出)。"""
    code = entry.get("code", "")
    expect_error = entry.get("expect_error", False)
    is_program = code.lstrip().startswith("package main")
    path = os.path.join(tmp, "main.go")

    builds = []
    for src in variants(code):
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
        builds.append((src, run(["go", "build", "./..."], tmp)))

    if expect_error:
        for src, build in builds:
            if build.returncode == 0:
                return False, "应当编译失败，但编译通过了", ""
        last = ""
        for src, build in builds:
            if build.stderr.strip():
                last = build.stderr.strip().splitlines()[-1][:120]
        return True, "应当编译失败 ✓", last

    ok_pair = next(((s, b) for s, b in builds if b.returncode == 0), None)
    if ok_pair is None:
        return False, "应当编译通过", builds[0][1].stderr.strip()[:400]

    src, _ = ok_pair
    extra = ""
    if is_program:
        prog = run(["go", "run", "."], tmp)
        if prog.returncode != 0:
            return False, "完整程序运行失败", prog.stderr.strip()[:400]
        extra = prog.stdout.strip()

    problem = gofmt_problem(src, tmp)
    if problem:
        return False, "gofmt 不规范", problem

    return True, "编译通过" + ("，运行通过" if is_program else ""), extra


def check_group_file(path, tmp):
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [("文件", False, "JSON 解析失败: %s" % e, "")]

    problems = []
    for field in REQUIRED_GROUP_FIELDS:
        if field not in data:
            problems.append(("字段", False, "分组缺少字段 %s" % field, ""))
    if problems:
        return problems

    expected_id = os.path.splitext(os.path.basename(path))[0]
    problems.append(
        ("标题", data["id"] == expected_id,
         "id = %s，应与文件名一致（%s）" % (data["id"], expected_id), "")
    )

    entries = data.get("entries", [])
    if not entries:
        problems.append(("条目", False, "分组没有任何条目", ""))
    if not any("组合示例" in e.get("title", "") for e in entries):
        problems.append(("组合示例", False, "末尾缺少「组合示例」条目", ""))

    for i, entry in enumerate(entries, 1):
        missing = [f for f in REQUIRED_ENTRY_FIELDS if f not in entry]
        if missing:
            problems.append((entry.get("title", "第 %d 条" % i), False,
                             "缺少字段 %s" % ", ".join(missing), ""))
            continue
        ok, msg, extra = check_entry(entry, tmp)
        problems.append((entry.get("title", "第 %d 条" % i), ok, msg, extra))

    return problems


def main():
    args = sys.argv[1:]
    categories = args if args else sorted(
        d for d in os.listdir(CONTENT_DIR)
        if os.path.isdir(os.path.join(CONTENT_DIR, d))
    )

    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    run(["go", "mod", "init", "verifytmp"], TMP)

    total_ok = 0
    total_bad = 0

    for category in categories:
        cat_dir = os.path.join(CONTENT_DIR, category)
        if not os.path.isdir(cat_dir):
            print("类别 %s 不存在，跳过\n" % category)
            continue

        files = sorted(f for f in os.listdir(cat_dir) if f.endswith(".json"))
        print("=== 类别 %s（%d 个分组）===" % (category, len(files)))

        for filename in files:
            path = os.path.join(cat_dir, filename)
            problems = check_group_file(path, TMP)
            group_bad = [p for p in problems if not p[1]]
            group_ok = [p for p in problems if p[1]]

            mark = "FAIL" if group_bad else "PASS"
            note = "，%d 项失败" % len(group_bad) if group_bad else ""
            print("  [%s] %s  (%d 项通过%s)" % (mark, filename, len(group_ok), note))

            for name, ok, msg, extra in problems:
                if not ok:
                    total_bad += 1
                    print("         ✗ %s: %s" % (name, msg))
                    if extra:
                        print("           %s" % extra)
            total_ok += len(group_ok)

        print()

    shutil.rmtree(TMP)

    print("通过 %d 项，失败 %d 项" % (total_ok, total_bad))
    sys.exit(1 if total_bad else 0)


main()
