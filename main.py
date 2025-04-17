import enum
import os
import argparse
from enum import Enum
from typing import Tuple


class Bytes:
    def __init__(self, x: bytes) -> None:
        self.__bytes = x

    @staticmethod
    def parse_to_str(x: bytes):
        return list(map(lambda x: hex(x).encode("utf-8"), list(x)))

    @staticmethod
    def parse(x: bytes) -> int:
        """big edian parser"""
        return sum(
            list(
                map(lambda e: (e[1] & 0xFF) << (8 * (len(x) - 1 - e[0])), enumerate(x))
            )
        )

    @staticmethod
    def __varint_progress(x: int) -> bool:
        return (x & 0b10000000) >> 7 == 1

    @staticmethod
    def varint(x: bytes, offset: int) -> Tuple[int, int]:
        res = []
        while Bytes.__varint_progress(x[offset]):
            res.append(x[offset])
            offset += 1

        res.append(x[offset])
        offset += 1

        res = int("".join(list(map(lambda x: "{:07b}".format(x & 0x7F), res))), 2)

        return (res, offset)

    def read_bytes_to_end(self) -> bytes:
        return self.__bytes

    def to_bytes(self, offset: int, size: int) -> bytes:
        return self.__bytes[offset : offset + size]

    def read_to_end(self):
        return Bytes.parse(self.__bytes)

    def read(self, offset: int, size: int) -> int:
        return Bytes.parse(self.__bytes[offset : offset + size])

    def read_to_string(self, offset: int, size: int):
        return self.__bytes[offset : offset + size].decode()


class Header:
    def __init__(self, header: bytes) -> None:
        bheader = Bytes(header)

        self.magic = bheader.read_to_string(0, 16)
        self.psize = bheader.read(16, 2)
        self.pages = bheader.read(28, 4)
        self.sqlite_version = bheader.read(96, 4)
        pass

    def __str__(self) -> str:
        public_attrs = {
            k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
            for k, v in vars(self).items()
            if not k.startswith("_")
        }
        return f"{public_attrs}"


class PageType(Enum):
    """
    InteriorIndex   0x02
    InteriorTable   0x05
    LeafIndex       0x0a
    LeafTable       0x0d
    """

    LeafIndex = 0x0A
    LeafTable = 0x0D
    InteriorIndex = 0x02
    InteriorTable = 0x05

    OverflowPage = 0xFF


class PageHeader:
    def __init__(self, content: Bytes, first: bool = False) -> None:
        if first:
            base = 100
        else:
            base = 0

        pgtype = content.read(base + 0, 1)
        if pgtype == 0x02:
            self.pgtype = PageType.InteriorIndex
            self.rmpointer = content.read(8, 4)
            self.cp_base = base + 12
        elif pgtype == 0x05:
            self.pgtype = PageType.InteriorTable
            self.rmpointer = content.read(8, 4)
            self.cp_base = base + 12
        elif pgtype == 0x0A:
            self.pgtype = PageType.LeafIndex
            self.cp_base = base + 8
        elif pgtype == 0x0D:
            self.pgtype = PageType.LeafTable
            self.cp_base = base + 8
        else:
            self.pgtype = PageType.OverflowPage
            self.next_page = content.read(base + 0, 4)
            return

        self.freeblock = content.read(base + 1, 2)
        self.cells = content.read(base + 3, 2)

        area = content.read(base + 5, 2)
        self.content_area = area if area != 0 else 65536
        self.fragmentbytes = content.read(base + 7, 1)

    def __str__(self) -> str:
        public_attrs = {
            k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
            for k, v in vars(self).items()
            if not k.startswith("_")
        }
        return f"{public_attrs}"


class Cell:
    def __init__(
        self, pgsize: int, pgtype: PageType, content: Bytes, coffset: int = 0
    ) -> None:
        bcontent = content.read_bytes_to_end()
        self.pgtype = pgtype

        if pgtype == PageType.LeafTable:
            payload_size, offset = Bytes.varint(bcontent, coffset)

            self.payload_size = payload_size
            rowid, offset = Bytes.varint(bcontent, offset)
            self.rowid = rowid

            if offset + payload_size <= pgsize:
                self.payload = content.to_bytes(offset, self.payload_size)
            else:
                self.payload = content.to_bytes(offset, self.payload_size - 4)
                offset += self.payload_size - 4

                # A 4-byte big-endian integer page number for the
                # first page of the overflow page list
                self.overflow_page_no = content.read(offset, 4)

        elif pgtype == PageType.InteriorTable:
            self.left_child_pointer = content.read(coffset, 4)
            coffset += 4
            int_key, offset = Bytes.varint(bcontent, coffset)
            self.int_key = int_key

        elif pgtype == PageType.LeafIndex:
            payload_size, offset = Bytes.varint(bcontent, coffset)
            self.payload_size = payload_size

            if offset + payload_size <= pgsize:
                self.payload = content.to_bytes(offset, self.payload_size)
            else:
                self.payload = content.to_bytes(offset, self.payload_size - 4)
                offset += self.payload_size - 4

                # A 4-byte big-endian integer page number for the
                # first page of the overflow page list
                self.overflow_page_no = content.read(offset, 4)

        elif pgtype == PageType.InteriorIndex:
            self.left_child_pointer = content.read(coffset, 4)
            coffset += 4

            payload_size, offset = Bytes.varint(bcontent, coffset)
            self.payload_size = payload_size

            if offset + payload_size <= pgsize:
                self.payload = content.to_bytes(offset, self.payload_size)
            else:
                self.payload = content.to_bytes(offset, self.payload_size - 4)
                offset += self.payload_size - 4

                # A 4-byte big-endian integer page number for the
                # first page of the overflow page list
                self.overflow_page_no = content.read(offset, 4)

        elif pgtype == PageType.OverflowPage:
            self.payload = content.to_bytes(coffset + 4, pgsize)

    def get_payload(self) -> bytes | None:
        if self.pgtype == PageType.InteriorTable:
            return None
        elif self.pgtype == PageType.OverflowPage:
            return self.payload
        else:
            return self.payload


class Page:
    def __init__(self, pgsize: int, content: Bytes, pgno: int) -> None:
        self.pgsize = pgsize
        self.pgno = pgno
        self.__content = content

        if pgno == 1:
            self.header = PageHeader(self.__content, first=True)
        else:
            self.header = PageHeader(self.__content)

        if self.header.pgtype != PageType.OverflowPage:
            cp_arr = content.to_bytes(self.header.cp_base, self.header.cells * 2)
            self.cell_ptrs = list(
                map(
                    lambda x: Bytes(bytes(x)).read_to_end(),
                    zip(cp_arr[::2], cp_arr[1::2]),
                )
            )

    def get_cell(self, cell_id: int = 1) -> None | Cell:
        if self.header.pgtype == PageType.OverflowPage:
            return Cell(
                self.pgsize,
                self.header.pgtype,
                self.__content,
            )
        if cell_id - 1 < self.header.cells:
            return Cell(
                self.pgsize,
                self.header.pgtype,
                self.__content,
                self.cell_ptrs[cell_id - 1],
            )
        return None

    def get_content(self) -> Bytes:
        return self.__content

    def __str__(self) -> str:
        public_attrs = {
            k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
            for k, v in vars(self).items()
            if not k.startswith("_")
        }
        return f"{public_attrs}"


class File:
    def __init__(self, path: str) -> None:
        self.__file = open(path, "rb")

        self.__file.seek(os.SEEK_SET)
        header = self.__file.read(100)
        self.__file.seek(os.SEEK_SET)

        self.header = Header(header)

        self.__file.seek(0)
        self.__pages = [
            Page(self.header.psize, Bytes(self.__file.read(4096)), i + 1)
            for i in range(self.header.pages)
        ]

    def close(self):
        self.__file.close()

    def __str__(self) -> str:
        public_attrs = {
            k: str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v
            for k, v in vars(self).items()
            if not k.startswith("_")
        }
        return f"{public_attrs}"

    def page(self, pgno: int) -> Page | None:
        if pgno - 1 < self.header.pages:
            return self.__pages[pgno - 1]
        return None


def main():
    parser = argparse.ArgumentParser(
        prog="parsley",
        description="parse an sqlite3 file",
    )
    parser.add_argument(
        "-d",
        "--dbfile",
        required=True,
        help="The db to be parsed",
    )
    args = parser.parse_args()

    db = File(args.dbfile)

    for j in range(db.header.pages):
        page = db.page(j + 1)
        if page is None:
            continue

        if page.header.pgtype != PageType.OverflowPage:
            print(
                f"[page {page.pgno}] {page.header.pgtype} with cells {page.header.cells}"
            )
            for i, _ in enumerate(page.cell_ptrs):
                cell = page.get_cell(i + 1)

                if cell is None:
                    continue

                print(f"\t[cell {i + 1}] {cell.get_payload()}")
        else:
            print(
                f"[page {page.pgno}] {page.header.pgtype} with next_page {page.header.next_page}"
            )
            cell = page.get_cell()
            if cell is not None:
                print(f"\t[payload] {cell.get_payload()}")


if __name__ == "__main__":
    main()
