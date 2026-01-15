import os
import random
import string

def gen_path(d=None):
    random_filename = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(10, 15)))+'.txt'
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    file_path = os.path.join(root, random_filename)
    return file_path, random_filename