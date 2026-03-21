# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import pytest
import sys
import os

# Add the parent directory to sys.path so we can import engines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from de4py.engines.onyx.string_decoder import StringDecoder


@pytest.fixture
def decoder():
    return StringDecoder()


def test_base64_decode(decoder):
    source = "x = base64.b64decode('SGVsbG8=')"
    result = decoder.decode_all(source)
    assert "'Hello'" in result or '"Hello"' in result


def test_eval_unwrap(decoder):
    source = "eval(\"print('hello')\")"
    result = decoder.decode_all(source)
    assert "eval" not in result
    assert "print" in result


def test_chr_chain(decoder):
    source = "x = chr(104)+chr(101)+chr(108)+chr(108)+chr(111)"
    result = decoder.decode_all(source)
    assert "hello" in result


def test_hex_escape(decoder):
    source = 'x = "\\x68\\x65\\x6c\\x6c\\x6f"'
    result = decoder.decode_all(source)
    assert "hello" in result


def test_xor_bytes(decoder):
    # bytes([72^0, 105^0]) = "Hi"
    source = "x = bytes([72, 105])"
    result = decoder.decode_all(source)
    assert "Hi" in result


def test_nested_eval(decoder):
    """eval wrapping eval wrapping base64"""
    source = "eval(\"base64.b64decode('cHJpbnQoJ2hpJyk=')\")"
    result = decoder.decode_all(source)
    assert "eval" not in result


def test_rot13(decoder):
    source = "x = codecs.decode('uryyb', 'rot_13')"
    result = decoder.decode_all(source)
    assert "hello" in result


def test_unchanged_clean_code(decoder):
    """Clean code should not be modified"""
    source = "def hello():\n    return 'world'\n"
    result = decoder.decode_all(source)
    assert result == source

