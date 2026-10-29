package site

import (
	"compress/gzip"
	"strings"

	"github.com/gin-gonic/gin"
)

// gzipMiddleware 用标准库压缩响应体。
//
// 详情页有几百 KB 的高亮 HTML，不压缩首次加载会明显慢。
// 这里没用 gin-contrib/gzip，是为了不给这个项目多加一个依赖。
func gzipMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !strings.Contains(c.GetHeader("Accept-Encoding"), "gzip") {
			c.Next()
			return
		}

		c.Header("Content-Encoding", "gzip")
		c.Header("Vary", "Accept-Encoding")
		// 压缩后长度变了，原来的 Content-Length 不能留
		c.Writer.Header().Del("Content-Length")

		writer := gzip.NewWriter(c.Writer)
		defer writer.Close()

		c.Writer = &gzipResponseWriter{ResponseWriter: c.Writer, writer: writer}
		c.Next()
	}
}

// gzipResponseWriter 把写入的内容交给 gzip 压缩后再发给客户端。
type gzipResponseWriter struct {
	gin.ResponseWriter
	writer *gzip.Writer
	size   int
}

func (w *gzipResponseWriter) Write(data []byte) (int, error) {
	n, err := w.writer.Write(data)
	w.size += n
	return n, err
}

func (w *gzipResponseWriter) WriteString(s string) (int, error) {
	n, err := w.writer.Write([]byte(s))
	w.size += n
	return n, err
}

// Size 返回压缩前的字节数，和 gin 自己的计数口径一致。
func (w *gzipResponseWriter) Size() int { return w.size }

func (w *gzipResponseWriter) Flush() {
	w.writer.Flush()
	w.ResponseWriter.Flush()
}

// 确认实现满足 gin 的接口要求。
var _ gin.ResponseWriter = (*gzipResponseWriter)(nil)
