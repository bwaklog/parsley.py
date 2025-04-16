# parsley.py

> SQlite3 db file parser following the [sqlite3 fileformat](https://sqlite.org/fileformat2.html)

## Running the project

1. Currently using the `uv` package manger: [link](https://github.com/astral-sh/uv)
2. Running the file

```fish
# fish.shell
uv venv
source .venv/bin/activate.fish

uv run main.py -h
```

```text
usage: parsley [-h] -d DBFILE

parse an sqlite3 file

options:
  -h, --help           show this help message and exit
  -d, --dbfile DBFILE  The db to be parsed
```


## References & Citations

- [sqlite.org/fileformat2.html](https://sqlite.org/fileformat2.html)
- [sqlite-internal.pages.dev](https://sqlite-internal.pages.dev/)
- [How does sqlite store data](https://michalpitr.substack.com/p/how-does-sqlite-store-data)
- [decoding varints](https://forum.codecrafters.io/t/sqlite-varint-decoding-stage-sz4/1934/2)
- [efficient variable length integers](https://john-millikin.com/vu128-efficient-variable-length-integers)
- [blog - reading sqlite schemas the hard way](https://www.philosophicalhacker.com/post/reading-sqlite-schema-tables-the-hard-way/)
