<a href="#home"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/de4py.jpg?raw=true"></img></a>
# de4py
<p align="center"><b>what is de4py?</b></p>
De4py are an Advanced python deobfuscator with a beautiful UI and a set of Advanced features that enables malware analysts and reverse engineers to deobfuscate python files and more. this project is maintained by me (<a href="https://github.com/Fadi002">Fadi002</a>) and my friend <a href="https://github.com/AdvDebug">AdvDebug</a>.

## Features
<table>
  <th align="left">Feature</th>
  <th align="left">Function</th>
  <tbody>
    <tr>
     <td>Deobfuscation</td>
     <td>De4py support some popular obfuscators, like: Jawbreaker, BlankOBF, PlusOBF, Wodx, Hyperion, pyobfuscate.com obfuscator</td>
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
    <tr>
      <td>GUI and Console Support</td>
      <td>De4py supports both console and GUI, but why use console when you can have a nice-on-the-eyes GUI, am i right? ;)</td>
    </tr>
    <tr>
      <td>File Analyzer</td>
      <td>an analyzer that have many features like detecting if the python program is packed and tries to unpack it if it was using pyinstaller for example, it also got a feature that shows either all strings or suspicious strings (suspicious strings like: IPs, websites, and "token" "discord" "leveldb" strings and other suspicious strings in the file) and shows them in a nice output window.</td>
    </tr>
    <tr>
      <td>Behavior Monitoring</td>
      <td>De4py can monitor python processes and see if they opened any files handles, opened a process, wrote/readed the memory of other processes and also monitoring if the process terminated other processes, in addition to sockets monitoring (including the size of data that is being sent and the ip that is being sent/recieved from) along with dumping socket content to a file and dumping OpenSSL encrypted content decrypted into a file.</td>
    </tr>
    <tr>
      <td>Plugins system</td>
      <td>You can add plugins to de4py to customize the theme or add custom deobfuscators <a href="https://github.com/Fadi002/de4py-plugins-repo">plugins repo and docs here</a></td>
    </tr>
    <tr>
      <td>API system</td>
      <td>You can use de4py features such as deobfusctor engine and pyshell in your own tools <a href="https://github.com/Fadi002/de4py/tree/main/api">API docs here</a></td>
    </tr>
  </tbody>
</table>

## Screenshots
<p float="left">
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Home.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Deobfuscator.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Shell.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/WinAPIHooking.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/Analyzer.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/About.png?raw=true" width="400"></img></a>
  <a href="#Screenshots"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/CLI.png?raw=true" width="400"></img></a>
</p>

## Contributions
All contributions are welcomed.

## Social media links
At this moment we have discord only https://discord.gg/cYxxUHsbRm

## Issues
Please before open issue read the [FAQ](https://github.com/Fadi002/de4py/blob/main/FAQ.md).

## Disclaimer
This tool are for educational purposes only, never try deobfuscating someone's software without permission, ALL developers and contributors are not responsible for any kind of misuse.

## License Notice
this tool are licensed under GNU General Public License v3.0.
