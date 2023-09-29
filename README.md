# de4py
<p align="center"><b>what is de4py?</b></p>
De4py are an Advanced python deobfuscator with a beautiful UI and a set of Advanced features that enables malware analysts and reverse engineers to deobfuscate python files and more.

## Features
<table>
  <th align="left">Feature</th>
  <th align="left">Function</th>
  <tbody>
    <tr>
     <td>Deobfuscation</td>
     <td>De4py support some popular obfuscators, like: Jawbreaker, BlankOBF, PlusOBF, Wodx</td>
    </tr>
    <tr>
      <td>Pycode Execution</td>
      <td>Executing your python code inside the process which can be useful in many cases to make the program do something you want to make it do, for example if the program have licensing and it calls the real "main" only if you bought the program you can call it directly.</td>
    </tr>
    <tr>
      <td>Strings Dump</td>
      <td>Dumping Strings in the python process and saving it as a file which can be pretty useful to extract data from memory such as webhooks.</td>
    </tr>
    <tr>
      <td>Removing Exit Function</td>
      <td>Removing the exit function which can be extremely useful if the python program tried to exit itself if it found a debugger or a VM</td>
    </tr>
    <tr>
      <td>Getting All Functions</td>
      <td>Getting all functions inside the python process which can be really useful when trying to modify a python function in memory</td>
    </tr>
    <tr>
      <td>Pyshell GUI</td>
      <td>Custom GUI to make it easy to execute python code inside the desired process.</td>
    </tr>
  </tbody>
</table>

## Screenshots
<a href="#home"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Home.png?raw=true"></img></a>
<a href="#about"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Deobfuscator.png?raw=true"></img></a>
<a href="#about"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Shell.png?raw=true"></img></a>
<a href="#about"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/About.png?raw=true"></img></a>
## Disclaimer
This tool are for educational purposes only, never try deobfuscating someone's software without permission, me (Fadi002) are not responsible for any kind of misuse.

## License Notice
this tool are licensed under GNU General Public License v3.0.
