#!/usr/bin/env python3
"""校验 content/ 下的所有内容文件。

对每个分组文件：
  - 校验 JSON 合法、字段齐全、没有未知字段
  - 把每条代码片段包成可编译单元，交给 Go 编译器
  - 标了 "expect_error": true 的条目必须编译失败（这类条目的教学点就是编译报错）
  - 完整程序（以 package main 开头）额外跑一遍
  - 检查 gofmt 规范
  - 代码片段型分组的「组合示例」必须存在且是最后一条
  - 每条条目必须有 description
  - 问答型条目：answer 3–6 点，标题是问句
  - expect_error 条目的 notes 要写清报错（否则用户不知道这段代码为什么编译不过）
  - 跨文件检查重复标题

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
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(ROOT, "content")

REQUIRED_ENTRY_FIELDS = ("title",)
REQUIRED_GROUP_FIELDS = ("id", "title", "entries")

# 允许出现的字段。写错字段名（比如 expect_err）会静默丢失，所以必须显式校验。
ALLOWED_GROUP_FIELDS = ("id", "title", "entries")
ALLOWED_ENTRY_FIELDS = (
    "title", "description", "code", "lang", "notes", "answer", "expect_error",
)

# 问答型条目的答案要点数量范围。
ANSWER_MIN, ANSWER_MAX = 3, 6

# 代码片段（非组合示例）的建议行数上限。Gin 需要完整服务骨架，放宽到 30 行；
# 组合示例是完整小程序，不受这个限制。
SNIPPET_MAX_LINES = {"gin": 30, "default": 10}

# 顶层 func 声明。函数体内不允许嵌套 func（方法和具名函数都不行），
# 所以含它们的片段要放到包级。type 声明在函数体内是合法的，不受影响。
TOP_LEVEL_FUNC = re.compile(r"^func\s", re.M)
HAS_MAIN = re.compile(r"^func main\(", re.M)

# 片段里可能用到的标准库包：包名 → 导入路径。
# 只在代码里真的出现 `pkg.` 时才加进 import，否则会报 unused import。
STDLIB = {
    "atomic": "sync/atomic",
    "bufio": "bufio",
    "bytes": "bytes",
    "cmp": "cmp",
    "context": "context",
    "csv": "encoding/csv",
    "embed": "embed",
    "errors": "errors",
    "fmt": "fmt",
    "http": "net/http",
    "httptest": "net/http/httptest",
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
    "sha256": "crypto/sha256",
    "slices": "slices",
    "slog": "log/slog",
    "sort": "sort",
    "sql": "database/sql",
    "strconv": "strconv",
    "strings": "strings",
    "sync": "sync",
    "testing": "testing",
    "time": "time",
    "tls": "crypto/tls",
    "unicode": "unicode",
    "url": "net/url",
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


def check_entry_shape(entry, category):
    """只检查字段和文字规范（不编译），返回 (problems, warnings)。"""
    problems, warnings = [], []
    name = entry.get("title", "?")
    title = str(entry.get("title", ""))

    unknown = [f for f in entry if f not in ALLOWED_ENTRY_FIELDS]
    if unknown:
        problems.append((name, False, "未知字段 %s" % ", ".join(unknown), ""))

    if not entry.get("description"):
        problems.append((name, False, "缺少 description", ""))

    # 问答型条目
    if entry.get("answer"):
        n = len(entry["answer"])
        if not ANSWER_MIN <= n <= ANSWER_MAX:
            problems.append(
                (name, False,
                 "answer 有 %d 点，应为 %d–%d 点" % (n, ANSWER_MIN, ANSWER_MAX), ""))
        if not title.rstrip().endswith(("？", "?")):
            problems.append((name, False, "问答条目的标题要写成问句（以？结尾）", ""))

    # 故意编译不过的条目，notes 里必须解释报错，否则用户不知道这是有意的
    if entry.get("expect_error"):
        notes = entry.get("notes", "")
        if not any(k in notes for k in ("报错", "编译不过", "panic")):
            problems.append(
                (name, False,
                 "expect_error 条目的 notes 要写清报错内容/原因", ""))

    # 片段长度只是建议，不判失败。问答型条目的代码是完整示例，不限制。
    code = entry.get("code")
    if code and not entry.get("answer") and "组合示例" not in title:
        limit = SNIPPET_MAX_LINES.get(category, SNIPPET_MAX_LINES["default"])
        lines = [line for line in code.splitlines() if line.strip()]
        if len(lines) > limit:
            warnings.append(
                (name, "代码 %d 行，超过建议的 %d 行" % (len(lines), limit)))

    return problems, warnings


def check_group_file(path, tmp, category):
    """返回 (problems, warnings)。problems 里的 ok 字段决定是否算失败。"""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [("文件", False, "JSON 解析失败: %s" % e, "")], []

    problems, warnings = [], []
    for field in REQUIRED_GROUP_FIELDS:
        if field not in data:
            problems.append(("字段", False, "分组缺少字段 %s" % field, ""))
    if problems:
        return problems, warnings

    for field in data:
        if field not in ALLOWED_GROUP_FIELDS:
            problems.append(("字段", False, "分组有未知字段 %s" % field, ""))

    expected_id = os.path.splitext(os.path.basename(path))[0]
    problems.append(
        ("标题", data["id"] == expected_id,
         "id = %s，应与文件名一致（%s）" % (data["id"], expected_id), "")
    )

    entries = data.get("entries", [])
    if not entries:
        problems.append(("条目", False, "分组没有任何条目", ""))

    # 代码片段型分组末尾要有「组合示例」，而且必须是最后一条；
    # 问答型分组（有 answer 的条目）不要组合示例。
    is_qa_group = any(e.get("answer") for e in entries)
    combo = [i for i, e in enumerate(entries) if "组合示例" in str(e.get("title", ""))]
    if not is_qa_group:
        if not combo:
            problems.append(("组合示例", False, "末尾缺少「组合示例」条目", ""))
        elif combo != [len(entries) - 1]:
            problems.append(
                ("组合示例", False,
                 "「组合示例」必须是最后一条（当前 %s，共 %d 条）"
                 % ("、".join("第 %d 条" % (i + 1) for i in combo), len(entries)), ""))
    elif combo:
        problems.append(("组合示例", False, "问答型分组不应有「组合示例」条目", ""))

    for i, entry in enumerate(entries, 1):
        name = entry.get("title", "第 %d 条" % i)
        missing = [f for f in REQUIRED_ENTRY_FIELDS if f not in entry]
        if missing:
            problems.append((name, False, "缺少字段 %s" % ", ".join(missing), ""))
            continue

        shape_problems, shape_warnings = check_entry_shape(entry, category)
        problems.extend(shape_problems)
        warnings.extend(shape_warnings)

        has_code = bool(entry.get("code"))
        has_answer = bool(entry.get("answer"))
        if not has_code and not has_answer:
            problems.append((name, False, "既没有 code 也没有 answer", ""))
            continue
        if has_code and not entry.get("lang"):
            problems.append((name, False, "有 code 但没有 lang", ""))
            continue

        if has_code:
            ok, msg, extra = check_entry(entry, tmp)
            problems.append((name, ok, msg, extra))
        else:
            problems.append((name, True, "问答条目", ""))

    return problems, warnings


def main():
    args = sys.argv[1:]
    categories = args if args else sorted(
        d for d in os.listdir(CONTENT_DIR)
        if os.path.isdir(os.path.join(CONTENT_DIR, d))
    )

    # 临时目录放在仓库外：仓库里的 go.work 会让嵌套模块的构建失败，
    # 而放在仓库外就完全不跟项目的模块设置打架。目录按进程隔离，
    # 多个校验同时跑也不会互相覆盖 main.go。
    TMP = tempfile.mkdtemp(prefix="verify_content_")
    # 复制仓库的 go.mod / go.sum：临时模块才有 gin、chroma 这些依赖，
    # 离线从模块缓存就能解析，不需要联网补依赖。
    for name in ("go.mod", "go.sum"):
        src = os.path.join(ROOT, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(TMP, name))

    total_ok = 0
    total_bad = 0
    total_warn = 0
    titles = {}          # 标题 → ["类别/文件 第 N 条", ...]，用来查重

    for category in categories:
        cat_dir = os.path.join(CONTENT_DIR, category)
        if not os.path.isdir(cat_dir):
            print("类别 %s 不存在，跳过\n" % category)
            continue

        files = sorted(f for f in os.listdir(cat_dir) if f.endswith(".json"))
        print("=== 类别 %s（%d 个分组）===" % (category, len(files)))

        for filename in files:
            path = os.path.join(cat_dir, filename)
            problems, warnings = check_group_file(path, TMP, category)
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

            for name, msg in warnings:
                total_warn += 1
                print("         ! %s: %s" % (name, msg))

            # 收集标题用于跨文件查重；组合示例的标题本来就重复，跳过
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                continue
            for i, entry in enumerate(data.get("entries", []), 1):
                title = str(entry.get("title", "")).strip()
                if not title or "组合示例" in title:
                    continue
                titles.setdefault(title, []).append(
                    "%s/%s 第 %d 条" % (category, filename, i))

        print()

    shutil.rmtree(TMP)

    dup = {t: where for t, where in titles.items() if len(where) > 1}
    if dup:
        print("=== 重复标题（%d 组）===" % len(dup))
        for title, where in sorted(dup.items()):
            print("  ✗ %s" % title)
            print("      出现位置：%s" % "；".join(where))
            total_bad += 1
        print()

    print("通过 %d 项，失败 %d 项，警告 %d 项" % (total_ok, total_bad, total_warn))
    sys.exit(1 if total_bad else 0)


if __name__ == "__main__":
    main()
