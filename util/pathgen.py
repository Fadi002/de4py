import os
import random
import string
def gen_path(d):
    random_filename = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(10, 15)))+'.txt'
    file_path = os.path.join(os.path.dirname(d), random_filename)
    return os.path.abspath(file_path), random_filename