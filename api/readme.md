# De4py API Documentation

## Analyzer API

The `Analyzer` class provides various methods for analyzing a file.

### Usage

```python
analyzer = Analyzer(file_path)

# Detect the packer used in the file
packer = analyzer.detect_packer()

# Get the file hashes (MD5, SHA1, SHA256)
hashes = analyzer.get_file_hashes()

# Unpack the file if it is packed with a supported packer
unpack_result = analyzer.unpack_file()

# Look up suspicious strings in the file
sus_strings = analyzer.sus_strings_lookup()

# Look up all strings in the file
all_strings = analyzer.all_strings_lookup()
```

### Methods

- `detect_packer() -> str`: Detects the packer used in the file.
- `get_file_hashes() -> str`: Gets the file hashes (MD5, SHA1, SHA256).
- `unpack_file() -> str`: Unpacks the file if it is packed with a supported packer.
- `sus_strings_lookup() -> Dict[str, list]`: Looks up suspicious strings in the file.
- `all_strings_lookup() -> str`: Looks up all strings in the file.

## Deobfuscator API

The `Deobfuscator` class is responsible for detecting and deobfuscating obfuscated code in Python files.

### Example Usage

```python
# Create an instance of the Deobfuscator class
deobfuscator = Deobfuscator()

# Shows a list of supported obfuscators
print(deobfuscator.supported_obfuscators_list)

# Automatically detect the obfuscator used in a Python file and deobfuscate it
file_path = "path/to/python/file.py"
deobfuscated_code = deobfuscator.auto_deobfuscator(file_path)
print(deobfuscated_code)

# Retrieve a specific deobfuscator based on its name
obfuscator_name = "pyobfuscate"
deobfuscator_info = deobfuscator.get_deobfuscator(obfuscator_name)
if deobfuscator_info is not None:
    name, regex_signature, deobfuscate_func = deobfuscator_info
    print(f"Deobfuscator Name: {name}")
    print(f"Regex Signature: {regex_signature}")
    print(f"Deobfuscate Function: {deobfuscate_func}")
else:
    print(f"No deobfuscator found with the name {obfuscator_name}")
```

## Pyshell API

The `Pyshell` class provides a wrapper API for interacting with the De4py Pyshell tool. It allows you to perform various operations on a target process, such as injecting the pyshell dll, executing Python files, and more.

### Example Usage

```python
# Create an instance of the Pyshell class
pyshell = Pyshell(process_pid=1234)

# Inject the pyshell dll into the target process
pyshell.inject()

# Execute a Python file in the target process
pyshell.execute_python_file('/path/to/python/file.py')

# Detach the shell from the target process
pyshell.deattach()
```

### Methods

- `show_hidden_console() -> bool`: Shows the hidden console of the target process.
- `inject() -> bool`: Injects the pyshell dll into the target process.
- `stealth_inject() -> bool`: Performs a stealth injection of the pyshell dll into the target process.
- `dump_strings() -> str`: Dumps strings from the target process and returns the filename of the dumped file.
- `get_all_functions() -> str`: Retrieves all functions from the target process and returns the filename of the retrieved file.
- `execute_python_file(file_path: str) -> bool`: Executes a Python file in the target process.
- `remove_exit_function() -> bool`: Removes the exit function from the target process.
- `deattach() -> bool`: Detaches the shell from the target process.
- `pyshell_gui() -> bool`: Launches the Pyshell GUI in the target process.
- `force_crash_process() -> bool`: Forces a crash in the target process.
