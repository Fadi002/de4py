import logging
from ast import NodeTransformer, parse, unparse
from typing import Any, Dict, Tuple, Type

from .transformers import *
from .transformers import constants


class Result:
    def __init__(self, code: str, passes: int, variables: Dict[str, Any]) -> None:
        self.code = code
        self.passes = passes
        self.variables = variables

    def add_variables(self) -> None:
        code = "\n".join(
            [f"{name} = {unparse(value)}" for name, value in self.variables.items()]
        )
        self.code = f"{code}\n{self.code}"


class Deobfuscator:
    TRANSFORMERS: Tuple[Type[NodeTransformer], ...] = (
        StringSubscriptSimple,
        GlobalsToVarAccess,
        InlineConstants,
        DunderImportRemover,
        GetattrConstructRemover,
        BuiltinsAccessRemover,
        Dehexlify,
        UselessCompile,
        UselessEval,
        ExecTransformer,
        UselessLambda,
        RemoveFromBuiltins,
    )

    AFTER_TRANSFORMERS: Tuple[Type[NodeTransformer], ...] = (
        LambdaCalls,
        EmptyIf,
    )

    def __init__(self, code: str) -> None:
        self.code = code
        self.tree = parse(code)

    def deobfuscate(self) -> Result:
        passes = 0
        code = self.code
        while True:
            for transformer in self.TRANSFORMERS:
                try:
                    self.tree = transformer().visit(self.tree)
                except Exception as e:
                    transformer_name = transformer.__name__
                    logging.warning(f"Transformer {transformer_name} failed with {e}")
            # If nothing changed after a full pass, we're done
            if (result := unparse(self.tree)) == code:
                for transformer in self.AFTER_TRANSFORMERS:
                    try:
                        self.tree = transformer().visit(self.tree)
                    except Exception as e:
                        transformer_name = transformer.__name__
                        logging.warning(
                            f"Transformer {transformer_name} failed with {e}"
                        )
                    code = unparse(self.tree)
                break
            code = result
            passes += 1
        return Result(code, passes, constants)
