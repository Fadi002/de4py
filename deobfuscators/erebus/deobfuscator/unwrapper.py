import ast
import logging
import zlib
from functools import reduce
from operator import add
from typing import List

logger = logging.getLogger(__name__)


class BlobFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.blobs: List[bytes] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if type(node.value) is bytes:
            self.blobs.append(node.value)

    def find_blobs(self, node: ast.AST) -> List[bytes]:
        self.visit(node)
        return self.blobs


def unwrap(code: str) -> str:
    """Find the actual code as a blob of obfuscated code"""
    tree = ast.parse(code)
    blobs = BlobFinder().find_blobs(tree)
    blob = reduce(add, blobs)
    logger.info(f"Found blob of length {len(blob)}")
    return zlib.decompress(blob).decode()
