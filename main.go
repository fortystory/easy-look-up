package main

import (
	"embed"
	"io/fs"
	"log"

	"github.com/fortystory/easy-look-up/internal/site"
)

//go:embed content
var contentFS embed.FS

func main() {
	fsys, err := fs.Sub(contentFS, "content")
	if err != nil {
		log.Fatal(err)
	}
	r, err := site.New(fsys)
	if err != nil {
		log.Fatal(err)
	}
	r.Run(":8080")
}
