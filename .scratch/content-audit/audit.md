# content/ 内容审查报告

- 审查对象：`content/` 下全部 62 个分组 JSON（10 个类别，908 条内容）
- 审查时间：2026-10-30
- 方法：`scripts/verify_content.py` 全量跑一遍 + 结构/规范脚本扫描 + 三路并行只读审查（Go/标准库/Gin；Go/并发/Gin 面试题；MySQL/Redis/Web/网络面试题）+ 关键结论本地实测复核
- 复核标记：✅ = 我用 Go 1.27.3 编译器、gin v1.12.0 源码或 MySQL 8.0 官方文档独立验证过

## 0. 结论

1. **机械层没问题**：970 项校验全部通过，24 个组合示例都能跑，JSON 结构、`id` 与文件名、`lang`、组合示例位置全合规。
2. **内容层有硬伤**：去重后约 **65 条事实错误**（含 5 条会导致复制出去的代码跑不通/结论错），另有约 **40 组重复内容**、**10 条故意编译不过的条目在页面上没有任何标记**。
3. **需要补充**：`go`/`stdlib`/`gin` 三个速查类别缺一批高频主题（测试、context、json、net/http 等），面试题各分类也有明确缺口。
4. **校验脚本有盲区**：组合示例位置、`answer` 条数、未知字段、重复标题、`expect_error` 的报错原因都没校验——上面多数问题脚本都不会报。

## 1. 机械校验结果（自动）

```
python3 scripts/verify_content.py
通过 970 项，失败 0 项
```

| 项目 | 结果 |
|---|---|
| JSON 合法 / `id` 与文件名一致 / 必填字段 | 全过 |
| 每条代码 Go 编译 | 全过 |
| 24 个组合示例（`package main`）实际运行 | 全过，退出码均为 0 |
| `expect_error` 条目必须编译失败 | 10/10 符合 |
| 组合示例位置（必须最后一条） | 24/24 在末位 |
| 代码缩进（tab）/ 注释中文 | 无违规 |
| 条目形态（同组不混用代码型与问答型） | 无违规 |
| `answer` 条数（3–6 点） | 无违规（实际 4–6 点） |

**脚本盲区**（以下问题脚本都不报，建议补进 `scripts/verify_content.py`）：

1. 组合示例只查「存在」，不查「必须是最后一条」。
2. 不校验未知字段——把 `expect_error` 拼成 `expect_err` 会静默通过。
3. 不校验 `answer` 3–6 点、问答标题必须是问句。
4. 不校验 `expect_error` 的失败原因——语法写错、忘了 import 也会算通过。
5. 不查重复标题（跨文件/分组）。
6. 不查 `description` 缺失（13 个面试分组全缺，见 §4）。
7. 不查 `3–8` 行片段长度限制（gin 分组几乎全部超，见 §4）。

## 2. 硬伤一：`expect_error` 在页面上没有任何标记

`docs/content-guide.md` 和 `spec.md` 都把 `expect_error` 定义为内容 schema 的一部分，但：

- `internal/content/content.go` 的 `Entry` 结构体没有这个字段，加载时直接丢弃；
- `internal/site/templates/detail.html` 没有渲染它。

后果：10 条**故意编译不过**的条目在页面上和普通条目长得一样，用户点「复制」会拿到一段编译失败、且不知道是故意的代码。

| 文件 | 条目标题 |
|---|---|
| [go/basic-types.json](content/go/basic-types.json) | 未使用的变量会编译报错 |
| [go/generics.json](content/go/generics.json) | 不能给具体类型加方法 |
| [go/generics.json](content/go/generics.json) | 接口方法不能带类型参数 |
| [go/interfaces.json](content/go/interfaces.json) | 接口里不能有字段 |
| [go/maps.json](content/go/maps.json) | 键必须是 comparable 类型 |
| [go/pitfalls.json](content/go/pitfalls.json) | 未使用的局部变量会编译报错 |
| [go/pointers.json](content/go/pointers.json) | 不能取结构体字面量的字段地址 |
| [go/structs.json](content/go/structs.json) | 指针接收者的方法不属于值类型 |
| [go/structs.json](content/go/structs.json) | 含切片的结构体不能比较 |
| [interview-go/design.json](content/interview-go/design.json) | Go 缺少哪些语言特性？分别要怎么绕过？ |

修法：`Entry` 加 `ExpectError bool \`json:"expect_error"\``，详情页在代码块旁加一个「这段代码会编译报错」徽标（复制按钮保留或加二次确认）。

另：`go/structs.json`「指针接收者的方法不属于值类型」notes 引用的报错文本过时——写的是 `(missing method Name)`，Go 1.27 实际是 `(method Name has pointer receiver)`。✅

## 3. 硬伤二：事实错误（约 65 条，按分类）

### 3.1 Go 语言 / 标准库 / Gin（20 条）

| 文件 | 条目标题 | 错在哪 | 应改成 |
|---|---|---|---|
| [go/loops.json](content/go/loops.json) | range 遍历 channel | notes 写 `for v, ok := range ch`；channel range 只允许一个变量，这行编译不过 ✅ | 用 `v, ok := <-ch`，或 `for v := range ch` |
| [go/basic-types.json](content/go/basic-types.json) | 短声明 := | 说明写「左边必须全是新变量，右边可以混着已有变量」，两句都错 ✅ | 左边**至少一个新变量**，其余可为同作用域已有变量 |
| [go/slices.json](content/go/slices.json) | 三索引切片 | `nums[1:3:4]` 的 cap=3，`append` 一个元素不会重分配、会直接写 `nums[3]`；notes 说反了 ✅ | 想挡住写穿用 `nums[1:3:3]`（cap=len） |
| [go/structs.json](content/go/structs.json) | 字段提升 | 「提升只穿透一层」不成立，多级嵌入会继续提升 ✅ | 可多级提升；被同名遮蔽时才写全路径 |
| [go/control-flow.json](content/go/control-flow.json) | 什么时候用 switch，什么时候用 if 链 | 「case 里只能写可比较的值，写不了复杂表达式」不成立 | case 是表达式（或条件），可写复杂表达式 |
| [go/maps.json](content/go/maps.json) | 遍历 map：顺序是随机的 | 「遍历中 delete 的键本次遍历可能还会被访问到」不成立 | 未遍历到的已删键不会再产出；规范允许遍历中删除 |
| [go/generics.json](content/go/generics.json) | 约束：any 与 comparable | notes 把 `<` 和 `==` 都归给 comparable | comparable 只有 ==/!=；排序比较要 cmp.Ordered |
| [go/generics.json](content/go/generics.json) | 用泛型实现 Map / Filter / Reduce | 「Go 1.23 起标准库 slices 里已经有 Map、Filter」不成立（没有这两个函数） | 标准库只有 Collect/Sorted 等；Map/Filter 要自己写 |
| [go/packages.json](content/go/packages.json) | go.mod：module 路径与 go 指令 | notes「写高了就用不了更新的语法」说反了 ✅ | go 指令是语言版本下限，写高才能用新特性 |
| [go/errors.json](content/go/errors.json) | errors.As 取出自定义错误 | 「第二个参数必须是指向指针类型的指针（**T）」是错的；传错是**运行时 panic**，不是编译错误 ✅ | 传「指向实现 error 的类型的指针」；必要时用 `errors.AsType` |
| [stdlib/errors.json](content/stdlib/errors.json) | errors.As：从错误链里取出自定义错误类型 | 同上，规则表述过窄 | 同上 |
| [stdlib/os.json](content/stdlib/os.json) | os.Stat 与 FileInfo：查文件属性 | Stat / Lstat 说反 | Stat 跟随符号链接，Lstat 描述链接本身 |
| [stdlib/os.json](content/stdlib/os.json) | os.Rename：改名和移动 | 「目标已存在时 Windows 会失败」不成立 | 已存在的非目录文件会被替换；目录报错；跨文件系统要复制再删 |
| [stdlib/strings.json](content/stdlib/strings.json) | strings.Builder：高效拼接字符串 | 「值拷贝共享 buffer、内容会串」不成立 | 复制非零 Builder 后再用会 panic，传参用 `*strings.Builder` |
| [stdlib/time.json](content/stdlib/time.json) | time.AfterFunc：到点自动执行回调 | 「回调里 panic 不会带崩主流程」不成立 | 回调在独立 goroutine，未 recover 的 panic 进程退出 |
| [stdlib/collections.json](content/stdlib/collections.json) | cmp.Compare 与 cmp.Or | 「任何可比较类型都能用」不成立 | 签名是 `Compare[T cmp.Ordered]` |
| [stdlib/collections.json](content/stdlib/collections.json) | maps.Keys、maps.Values 与 maps.Clone | 「1.21/1.22 里直接返回切片」不成立（1.23 才进标准库且返回 iter.Seq） | 删掉 1.21/1.22 说法，或注明 x/exp/maps |
| [gin/basics.json](content/gin/basics.json) | 路由组里的中间件 | notes 说忘了 `c.Next()` 链就断；引擎已调用过一次 Next，不写 Next 后续 handler 照跑，只有 Abort 截断 ✅ | 改成「不写 Next 不会阻断；要阻断用 Abort」 |
| [gin/basics.json](content/gin/basics.json) | 创建引擎：gin.Default() 与 gin.New() | 「New() 不挂 Recovery，panic 会直接带崩进程」不成立 | 连接 goroutine 会被 net/http recover，该请求中断、进程不崩 |
| [gin/static.json](content/gin/static.json) | 自定义 404 r.NoRoute | 「gin 默认 404 响应体是空的」不成立 ✅ | 默认返回 404 + `404 page not found`；空 body 是静态文件处理器的 404 |
| [gin/response.json](content/gin/response.json) | c.HTML：渲染 HTML 模板 | 「模板名没注册会 panic」不成立 ✅ | 返回错误、写入 `c.Errors` 并 Abort，状态码保持传入值 |

### 3.2 interview-go / interview-concurrency / interview-gin（25 条）

| 文件 | 条目标题 | 错在哪 | 应改成 |
|---|---|---|---|
| [interview-concurrency/governance.json](content/interview-concurrency/governance.json) | 什么是「超时传递」？为什么上游的超时要小于下游的超时？ | 标题与正文结论相反：应「上游超时 > 下游超时」，逐层收紧 | 改标题为「为什么上游的超时要大于下游」 |
| [interview-concurrency/distributed.json](content/interview-concurrency/distributed.json) | Redlock 算法有什么争议？ | 「全部节点成功才算加锁」错 | 多数派（N/2+1）成功且总耗时小于租约 |
| [interview-redis/lock.json](content/interview-redis/lock.json) | Redlock 算法具体是怎么做的？Redis Cluster 能当 Redlock 用吗？ | 同上，answer 和 notes 都把「全部节点」当标准答案；「过半是 etcd 口径」也不对 | 同 Redlock 修正 |
| [interview-go/stdlib.json](content/interview-go/stdlib.json) | log/slog 和老的 log 包有什么区别？ | 「默认写 JSON」错 | 默认 handler 输出文本到 stderr；JSON 要 `NewJSONHandler` |
| [interview-go/stdlib.json](content/interview-go/stdlib.json) | io.Reader / io.Writer 有哪些常用组合器？ | 标准库没有 `io.LimitWriter` | 删掉，或改「LimitReader + 自定义 Writer」 |
| [interview-go/runtime.json](content/interview-go/runtime.json) | 什么是协作式抢占？ | 把「循环回边」列为安全点；1.14 之前恰恰没有 | 安全点是函数入口栈增长检查等 |
| [interview-go/runtime.json](content/interview-go/runtime.json) | goroutine 阻塞的时候，P 是交给别人还是继续占着 M？ | 「用户态阻塞时把 M 让出来，P 始终绑在这个 M 上」自相矛盾 | channel/锁阻塞只换 G 不释放 M；释放 P 的是 syscall handoff |
| [interview-go/runtime.json](content/interview-go/runtime.json) | GOMAXPROCS 是什么？ | 「IO 密集适当调大以掩盖等待」误导 | IO 阻塞自动让出 P，按 CPU 核数配 |
| [interview-go/basics.json](content/interview-go/basics.json) | defer 什么时候执行？ | 「主 goroutine 直接结束不会执行 defer」错 | main 正常返回会执行 main 的 defer；只有 os.Exit/fatal 跳过 |
| [interview-go/basics.json](content/interview-go/basics.json) | Go 的零值是什么？ | 「HTTP 客户端要靠构造函数返回」错 | http.Client 零值可用；sql.DB 才需要构造 |
| [interview-go/basics.json](content/interview-go/basics.json) | string、byte、rune 有什么区别？ | 「string 内容保证是合法 UTF-8」错 | string 是任意字节序列，只有字面量保证合法 |
| [interview-go/basics.json](content/interview-go/basics.json) | 为什么接口里明明是 nil，err != nil 却成立？ | 示例 `return (*MyError)(nil), nil` 与结论矛盾 | 应写成 `return (*MyError)(nil)`（唯一 error 返回值） |
| [interview-go/basics.json](content/interview-go/basics.json) | map 的遍历顺序为什么是随机的？ | 「Go 1.12 之后才允许遍历时删 key」错 | 规范从一开始就允许 |
| [interview-go/design.json](content/interview-go/design.json) | Go 为什么不支持异常… | 「panic 跨 goroutine 边界传播」错 | panic 不跨 goroutine，未 recover 直接进程退出 |
| [interview-go/design.json](content/interview-go/design.json) | Go 缺少哪些语言特性？ | 「没有包级可见性控制」错 | 用首字母大小写控制 |
| [interview-go/design.json](content/interview-go/design.json) | 什么时候该用指针接收者？ | 「值接收者让类型保持可比较」错 | 接收者形式不影响可比较性 |
| [interview-go/design.json](content/interview-go/design.json) | 泛型解决了什么问题？ | 正文「编译期展开、无额外开销」与 notes 的 GC shape 字典化矛盾 | 按 GC shape 生成 + 字典，不是完全单态化 |
| [interview-go/memory.json](content/interview-go/memory.json) | sync.Pool 里的对象和 GC 是什么关系？ | 「New 必须给」错，与 concurrency 分组矛盾 | Pool 零值可用，New 可为 nil，Get 可能返回 nil |
| [interview-concurrency/metrics.json](content/interview-concurrency/metrics.json) | 一次压测要分哪几个阶段？ | 「Go 的 GC、连接池、JIT、缓存都需要时间」——Go 没有 JIT | 删掉 JIT |
| [interview-concurrency/metrics.json](content/interview-concurrency/metrics.json) | P99 延迟是什么？ | 「vegeta、wrk2、hey 都基于 HDR Histogram」错 | vegeta 是自研分桶 histogram |
| [interview-concurrency/troubleshoot.json](content/interview-concurrency/troubleshoot.json) | 锁竞争怎么发现？pprof 的 mutex profile 有什么用？ | 说有两类样本 delay/hold | 只有 contentions + delay，持锁时间要靠 trace |
| [interview-gin/engineering.json](content/interview-gin/engineering.json) | Gin 的 Context 为什么不能跨 goroutine 用？ | 「c.Copy() 的 Keys 深拷贝」错 | v1.12 用 maps.Clone，浅拷贝 |
| [interview-gin/routing.json](content/interview-gin/routing.json) | Gin 的路由树是怎么匹配的？ | 「标准库 1.22 起没有 catch-all」错 | Go 1.22 ServeMux 支持 `{path...}` |
| [interview-go/stdlib.json](content/interview-go/stdlib.json) | regexp 为什么强调预编译？ | 「Go 1.11 起支持命名捕获组 (?P<name>...)」版本说错 | 该语法早于 1.11；1.22 新增 `(?<name>...)` |
| [interview-go/stdlib.json](content/interview-go/stdlib.json) | time.Duration 是什么？… | 「不要用 == 或 >」——time.Time 不支持 `>` | 先后用 Before/After |
| [interview-go/stdlib.json](content/interview-go/stdlib.json) | encoding/json 的 struct tag 怎么用？ | 「map 键必须是字符串或 TextMarshaler」漏了整数键 | 补充整数类型键 |

### 3.3 MySQL / Redis / Web / 网络（25 条）

| 文件 | 条目标题 | 错在哪 | 应改成 |
|---|---|---|---|
| [interview-mysql/engine.json](content/interview-mysql/engine.json) | Buffer Pool 是什么？/ checkpoint / 8.0 redo 容量（3 条共同出错） | 「innodb_io_capacity 8.0.20 起默认从 100 提到 2000」——默认值一直是 **200**，2000 是 `innodb_io_capacity_max` ✅ | 默认 200；2000 是 max |
| [interview-mysql/engine.json](content/interview-mysql/engine.json) | Buffer Pool / 8.0 redo 容量 | `innodb_read_io_concurrency` 参数名待核（8.0 参数表里读 IO 线程是 `innodb_read_io_threads`） | 复核参数名再写 |
| [interview-mysql/engine.json](content/interview-mysql/engine.json) | binlog 有哪三种格式？ | 「mixed 5.7.7 引入、5.7.7–8.0 默认」错 | mixed 自 5.1.5；5.7.7 是把默认从 statement 改成 row |
| [interview-mysql/transaction.json](content/interview-mysql/transaction.json) | Read Committed 和 Repeatable Read… | 「statement 格式要求 RC 及以上、RC 更安全」方向反了 | SBR 配 RR 才安全；RC 一般配 row |
| [interview-mysql/lock.json](content/interview-mysql/lock.json) | InnoDB 的行锁是怎么加的？ | 「RC 下语句一结束就释放锁」不准确 | 只释放未命中行的锁，命中行持有到事务结束 |
| [interview-mysql/index.json](content/interview-mysql/index.json) | 为什么 MySQL 的索引用 B+ 树… | notes 称「8.0.13 起支持哈希索引」 | InnoDB 不支持用户建 HASH 索引；8.0.13 加的是不可见索引 |
| [interview-mysql/lock.json](content/interview-mysql/lock.json) | 死锁是怎么产生的？ | 「innodb_deadlock_detect 8.0.3 起已废弃」错 | 8.0 仍是有效动态参数，默认 ON |
| [interview-mysql/lock.json](content/interview-mysql/lock.json) | 哪些语句会加表锁？ | notes 称 TRUNCATE「以行格式写进 binlog」 | DDL 始终以 statement 记录 |
| [interview-mysql/index.json](content/interview-mysql/index.json) | InnoDB 是怎么把数据和索引存到磁盘上的？ | 「NULL 列表可以放到溢出页」错 | NULL 位图在行头；只有变长列可溢出 |
| [interview-mysql/optimization.json](content/interview-mysql/optimization.json) | 慢查询日志怎么开？ | 把 log_output 也算进「默认 OFF」 | log_output 默认 FILE；5.7 默认 OFF 的只有 slow_query_log |
| [interview-redis/datatype.json](content/interview-redis/datatype.json) | String 的整数编码和 embstr 编码分别是什么？ | 「int 编码也用 embstr 存十进制字符串」，与同题第 2 点矛盾 | int 编码直接存指针 |
| [interview-redis/datatype.json](content/interview-redis/datatype.json) | List 的底层结构是什么？ | 「list-max-listpack-size 默认 128 字节」错 | 默认 -2（单节点 8KB） |
| [interview-redis/datatype.json](content/interview-redis/datatype.json) | Set 的底层结构是什么？ | 只列 intset/hashtable | Redis 7.2 起还有 listpack 编码 |
| [interview-redis/cache.json](content/interview-redis/cache.json) | 什么是大 key？ | 「FREETRUNC（6.2 起）」——无此命令 | 大 string 用 DEL/UNLINK 或覆盖重建 |
| [interview-redis/ops.json](content/interview-redis/ops.json) | 慢查询日志（SLOWLOG）怎么用？ | 「0 关闭、负数记录所有」反了 | 0 记录所有命令，负数是关闭 |
| [interview-redis/lock.json](content/interview-redis/lock.json) | 怎么用 Redis 实现排行榜？ | 「同分并列同名次」错 | ZREVRANK 返回 0 基排名，同分按 member 字典序 |
| [interview-web/browser.json](content/interview-web/browser.json) | defer 和 async 有什么区别？ | 「async 下载慢会拖住 DOMContentLoaded」错 | async 不阻塞；defer 会被等待 |
| [interview-web/browser.json](content/interview-web/browser.json) | 页面加载性能指标有哪些？ | 「2024 年起 LCP 取代 FCP」错 | LCP 2020 就是 CWV；2024 是 INP 取代 FID |
| [interview-web/browser.json](content/interview-web/browser.json) | 事件循环里宏任务和微任务的执行顺序 | 第 6 点「排在清空之后，也就是下一个宏任务之前」自相矛盾 | 宏任务里产生的 then 在同一轮检查点执行 |
| [interview-web/http.json](content/interview-web/http.json) | HTTP/2 的多路复用和二进制分帧… | 「RFC 9213 改用可扩展优先级」错 | 是 RFC 9218；9213 是 Targeted HTTP Cache Control |
| [interview-web/security.json](content/interview-web/security.json) | XSS 是什么？有哪几类？ | notes 称 innerHTML「会执行里面的 script 标签」错 | 插入的 script 不执行；执行的是事件属性、javascript: |
| [interview-web/performance.json](content/interview-web/performance.json) | 预加载和预渲染分别用在哪？ | 「Chrome 支持 rel=prerender」已过时 | Chrome 63 起移除，改用 Speculation Rules |
| [interview-network/tcp.json](content/interview-network/tcp.json) | TCP 的校验和是怎么算的？ | 「IPv4 头校验和可选、IPv6 强制」错 | IPv4 头校验和强制；IPv6 头没有校验和 |
| [interview-network/dns-tls.json](content/interview-network/dns-tls.json) | 自签名证书和 CA 签发证书有什么区别？ | 「公开证书最长 398 天（2020 起）」已过时 | 2026-03-15 起上限 200 天 |
| [interview-network/io-model.json](content/interview-network/io-model.json) | 什么是零拷贝？ | MSG_ZEROCOPY 标成 4.1；「省 2 次拷贝/2 次系统调用」错误 | 4.14；sendfile 省 2 次拷贝、2 次上下文切换、1 次系统调用 |
| [interview-network/dns-tls.json](content/interview-network/dns-tls.json) | 为什么 HTTPS 用 TCP 而不是 UDP？ | 「HTTP/3 是 QUIC 0-RTT」误导 | 首次连接仍 1-RTT，0-RTT 只用于会话恢复 |

## 4. 硬伤三：重复与边界

### 4.1 同一类别内重复（go / gin）

- [gin/basics.json](content/gin/basics.json)「路由冲突会 panic」与 [gin/static.json](content/gin/static.json)「路由冲突会 panic」**同名条目**，示例几乎相同。
- [gin/basics.json](content/gin/basics.json)「自定义 404 与 405」与 [gin/static.json](content/gin/static.json) 的「自定义 404 r.NoRoute」「自定义 405 r.NoMethod」同一 API 拆在三处。
- [gin/basics.json](content/gin/basics.json)「引擎中间件：r.Use / 路由组里的中间件」与 [gin/middleware.json](content/gin/middleware.json) 的「注册全局中间件 / 路由组中间件」重复；中间件洋葱模型在 middleware 组内还有 3 条重复。
- [gin/binding.json](content/gin/binding.json) 的 ShouldBind / ShouldBindJSON / BindJSON 对比 / 绑定失败返回 400 四条结论高度重叠。
- [go/pitfalls.json](content/go/pitfalls.json) 与其它分组：未使用变量、导出规则、多返回值、包名/文件名/目录名四处是搬运。
- [go/errors.json](content/go/errors.json) 与 [stdlib/errors.json](content/stdlib/errors.json)：自定义错误类型、errors.As、哨兵错误、%w 各写一遍；按规范（标准库归 stdlib）`go` 类别不该覆盖这些 API。
- [go/generics.json](content/go/generics.json) 的「标准库：slices 包」「标准库：maps 与 cmp 包」与 [stdlib/collections.json](content/stdlib/collections.json) 重复，同时违反「标准库不写进 go 类别」的边界。
- 另有 go 内部小重复：control-flow 的 if 链两条、maps 与 loops 的 range 语义、os 的 bufio.Scanner 两条、collections 的排序两条。

### 4.2 跨分类重复（interview-*）

- **Redlock**：`redis/lock` ↔ `concurrency/distributed`（同一题目，两处都错）。
- **幂等** 4 处：`concurrency/architecture`、`concurrency/distributed`（2 条）、`concurrency/scenarios`、`web/api`、`redis/lock`。
- **限流** 4 条：`web/api` ↔ `concurrency/governance`。
- **缓存穿透/击穿/雪崩**：`redis/cache` ↔ `concurrency/architecture`。
- **HTTP 缓存**：`web/http` ↔ `web/performance` ↔ `web/browser`。
- **CORS**：`web/browser` ↔ `web/security`（security 内部还有 4 条互相复述）。
- **死锁排查**：`concurrency/troubleshoot` 2 条 ↔ `go/runtime` 1 条（all goroutines are asleep）。
- **pprof**：`go/performance` ↔ `go/memory` ↔ `concurrency/troubleshoot` ↔ `go/runtime`（heap/mutex/trace 分散在 4 个文件）。
- **sync.Pool** 3 处：`go/concurrency` ↔ `go/memory` ↔ `go/performance`。
- **逃逸分析** 3 处：`go/memory`（2 条）↔ `go/performance`。
- **http.Server 超时**：`go/stdlib` ↔ `interview-gin/engineering`（同一组 ReadTimeout/WriteTimeout/IdleTimeout）。
- **Recovery 中间件** 4 处：`gin/response`（2 条）↔ `gin/routing` ↔ `gin/engineering`。
- **Context 复用/跨 goroutine**：`gin/routing` ↔ `gin/engineering`。
- **限制请求体大小**：`gin/binding` ↔ `gin/engineering`。
- **压测**：`gin/engineering` ↔ `concurrency/metrics`。
- **雪花算法/全局唯一 ID**：`concurrency/distributed` ↔ `concurrency/scenarios`。
- **定时任务只执行一次**：`concurrency/distributed` ↔ `concurrency/scenarios`。
- **超时设置**：`concurrency/governance`（2 条）↔ `concurrency/troubleshoot`。
- **TIME_WAIT**：`network/tcp` ↔ `network/troubleshoot`。

（`concurrency` 6 个文件里没有独立 GMP 条目，**不**构成重复。）

## 5. 规范不一致

1. **13 个面试分组完全没有 `description`**（189 条）：`interview-concurrency/{distributed,governance,scenarios,troubleshoot}`、`interview-go/{concurrency,design,memory,tooling}`、`interview-mysql/index`、`interview-network/troubleshoot`、`interview-redis/{cache,datatype,persistence}`。其余 25 个面试分组都有，详情页视觉不齐。
2. **2 条问答标题不是问句**：`interview-mysql/transaction`「事务是怎么提交的？redo log 的两阶段提交讲一下。」、`interview-network/tcp`「TCP 是怎么保证数据不丢的？确认和重传机制讲一下。」
3. **固定 6 点凑数**：295 条面试题里 293 条正好 6 点，出现「答题要点」「常见误区」这类非知识点；`interview-mysql/engine`「5.5 之后默认 InnoDB」第 6 点就是「答题要点」。
4. **notes 双要素缺失**：36 条只写追问、没写「常见错误回答」（Redis lock/persistence/ops 集中 29 条），不符合 guide 对 notes 的要求。
5. **答案要点过长**：107 条要点超过 120 字，最长 192 字（含多句/多命令），与「一句话、可扫读」冲突；`interview-mysql/availability`「监控要盯哪些指标」单点塞 5–8 个变量。
6. **单条不自足**：`interview-mysql/transaction` 写「具体见下一题」、`interview-web/api` 写「见并发治理那组」、`interview-redis/lock` 写「通用分布式锁理论见…」，面试答题等于没答。
7. **`3–8 行` 片段限制与现实不符**：`gin` 5 个分组几乎每条都超 10 行（最长 46 行）；面试题带代码的 172 条里有 44 条超过 30 行（最长 83 行）。建议 guide 明确「Gin 因需完整服务骨架可放宽到 30 行内；问答型代码示例同上」。
8. **内部矛盾**：`interview-go/runtime` 一处说「初始栈 2KB（_StackMin）」，另一处说「1.19 起自适应、2KB 只是下限」——后者与 Go 源码一致 ✅，前者需要加版本限定。
9. `go/generics` 有一处提到「Go 1.27 起方法可带类型参数」——本机 go1.27.3 实测**支持** ✅，这条是对的。
10. JSON 字段顺序在文件间有 3 种排列（不影响功能，只影响 diff 噪音）。

## 6. 需要补充的内容

### 6.1 速查类别（优先）

- **go**：缺「测试」（`go test`、表驱动、benchmark、`t.Chdir`）和「context」两个高频分组；建议补「数组」「iota / 类型定义 vs 类型别名」；`concurrency` 缺 context 取消/超时、sync.Once、atomic；`interfaces` 缺接口嵌入/组合。
- **stdlib**：缺 `context`、`encoding/json`、`net/http`、`regexp`、`log/slog`、`sync/atomic`、`flag`、`testing`。数据依据：面试题里 `pprof` 出现 23 次、`atomic`/`errgroup` 各 5 次，速查分类 0 条。
- **gin**：缺 Cookie/Session、文件上传（`FormFile`）、`httptest` 测试、CORS、`SetTrustedProxies`/`ClientIP`、`PureJSON`/`FileAttachment`、`ShouldBindBodyWith`、`binding:"dive"`、`c.Copy()`。

### 6.2 面试题分类（按缺口清单）

- **interview-go**：sync.Cond、内存模型/happens-before、struct 内存对齐、slices/maps/embed/database/sql、go.work/vendor/GOPROXY、PGO 与编译器优化、runtime/metrics 与 GODEBUG。
- **interview-concurrency**：TCC/Saga/本地消息表、Raft/Paxos、缓存一致性专题（延迟双删、Cache Aside 并发写）。
- **interview-gin**：测试专题、CORS/JWT/限流/Prometheus 中间件实现。
- **interview-mysql**：自增锁与自增值不连续、Online DDL 三种算法与 MDL、优化器统计信息与 8.0 直方图。
- **interview-redis**：ACL 与安全基线、7.x 新特性（Functions、client-side caching/RESP3、sharded pub/sub）、Cluster 扩缩容与故障转移实操。
- **interview-web**：WebSocket/SSE、OAuth2/OIDC 授权码 + PKCE、第三方 Cookie 淘汰与存储分区。
- **interview-network**：容器网络（netns/veth/bridge/Calico）、L4/L7 负载均衡与反向代理、SYN 重传参数与半连接超时。
- 可选新类别：Linux/操作系统、消息队列（Kafka/RocketMQ）、系统设计——是否加由项目范围决定。

## 7. 建议修复顺序

1. **先补工具盲区**：给 `verify_content.py` 加 §1 的 7 条检查，让重复/字段/条数问题以后自动暴露。
2. **修事实错误**：§3 的 65 条按文件批量改，改完重跑校验。
3. **接上 `expect_error`**：内容包 + 模板 + 测试，10 条条目在页面上有徽标。
4. **去重**：§4.1 先处理 gin 同类别同名条目和 go/errors ↔ stdlib/errors 边界，再处理面试题跨分类重复（可保留一处、另一处改为链接式引用）。
5. **补内容**：§6.1 速查类别（测试、context、json、net/http 优先），再按 §6.2 补面试题。
6. **统一规范**：补 13 个分组的 description、改 2 条标题、把固定 6 点改成按需 3–6 点、更新 `docs/content-guide.md` 的片段长度限制。

## 8. 审查覆盖说明

- 三路审查各自覆盖：`go`+`stdlib`+`gin` 24 个分组（20 条事实错误）、`interview-go`+`interview-concurrency`+`interview-gin` 18 个分组（25 条）、`interview-mysql`+`interview-redis`+`interview-web`+`interview-network` 20 个分组（25 条）。
- 每路都要求「没有问题的部分明确写无」；三路都确认了各自范围内格式与结构的合规性。
- 我额外复核了 12 条关键结论（Go 编译器实测 5 条、gin 源码 4 条、MySQL 官方文档 1 条、Go 源码 1 条、内容原文 1 条），并补充了 `expect_error` 渲染缺失、innodb_io_capacity 错误、13 组缺 description 等报告外的发现。

---

# 处理结果（2026-10-30 修复完成）

## 最终状态

- `content/` 从 62 个分组扩到 **71 个**（新增 9 组），条目从 908 条增到 **1040 条**。
- `python3 scripts/verify_content.py`：**通过 1111 项，失败 0 项，警告 82 项**（警告全是「代码超过建议行数」，gin/标准库的完整程序不可避免）。
- `go build ./...`、`go test ./internal/...` 通过；新增真实内容冒烟测试 `TestAllRealCategoriesRender`，10 个类别全部能渲染。
- 工作区无越界改动：只动了 `content/`、`docs/content-guide.md`、`README.md`、`internal/`、`scripts/verify_content.py`。

## 已修（对应上文各节）

1. **事实错误**：§3 的 65 条全部修完，另修了审查报告之外发现的 4 处：`innodb_io_capacity` 默认值（200）、`WRITESET` 版本口径（8.0.1 支持、8.0.27 改默认）、`innodb_max_dirty_pages` 参数名、`go/structs` 引用的旧报错文本。所有修改以 Go 1.27.3 编译器、gin v1.12.0 源码、MySQL 8.0 官方文档或本地实测为准。
2. **`expect_error` 渲染**：`content.Entry` 增加 `ExpectError` 字段，详情页显示红色「这段代码是故意编译不过的」标记，补了 content/site 测试和亮暗两套主题样式。
3. **校验脚本增强**：未知字段、组合示例必须在最后一条、`description` 必填、问答标题问句、`answer` 3–6 点、`expect_error` 的 notes 必须写报错、跨文件重复标题、片段长度警告。同时补全自动 import 表（net/http、httptest、log/slog、sync/atomic、testing、embed、database/sql 等）。
4. **去重**：gin/basics ↔ static（同名冲突条目改名、404/405 合并）、gin/basics ↔ middleware（中间件机制只留 middleware）、gin/binding 四条重叠合并成两条、go/pitfalls 四条搬运换成独有坑、go/errors ↔ stdlib/errors 按类别边界拆分、go/generics 里的标准库条目移出、web/security 的 CORS/CSRF/XSS 四条合并成两条、redis datatype/ops/lock 的重复条目合并、tcp/troubleshoot 的 TIME_WAIT 分工、interview-gin 的 Recovery/Context/请求体/超时/压测合并。
5. **规范**：13 个面试分组补齐 `description`（189 条）；2 条非问句标题改成问句；36 条 notes 补「常见错误回答」；删掉「答题要点/常见误区」占到点数；精简 107 条超过 120 字的答案要点；JSON 字段顺序统一为 `title, description, answer, code, lang, notes`。
6. **内容补充**：新增 `go/testing`、`stdlib/context`、`stdlib/json`、`stdlib/http`、`stdlib/log`、`stdlib/regexp`、`stdlib/atomic`、`gin/cookies`、`gin/testing` 9 个分组；go 的 basic-types/interfaces/concurrency/packages、gin 的 basics/binding/middleware/response 各追加 1–3 条；面试题 9 个分类按 §6.2 缺口清单共追加 26 条。

## 已知保留项（有意的取舍）

- **跨分类重复保留**：幂等（4 处）、限流（4 条）、缓存穿透/击穿/雪崩、pprof 分工、Redlock 两处，都是不同面试分类的不同提问角度，只修事实、不删内容。
- `gin/response` 的「c.JSON 的状态码写法」被替换成「c.PureJSON」以控制条目数，409/422 这类状态码清单随条目移除。
- `go/concurrency` 追加 3 条后为 18 条，超出其它分组的 13–17 条区间。
- `go/testing` 与 `gin/testing` 的组合示例是「可运行的手写断言/httptest」折中版本，因为校验脚本要求组合示例能 `go run`，而 testing.T 无法在普通 main 里构造；notes 里已说明真实项目用 `go test`。
- 82 条行数警告：gin 完整服务骨架、标准库 httptest 完整程序、atomic/log 的完整程序无法压到 10 行以内，已更新 `docs/content-guide.md` 说明例外。
- 未新增：Prometheus/限流中间件的完整实现（依赖外部包）、database/sql 的独立条目（Gin 连接池条目已覆盖）。
- `interview-go/tooling`、`interview-go/stdlib` 等条目数到 17，仍在上限内。
