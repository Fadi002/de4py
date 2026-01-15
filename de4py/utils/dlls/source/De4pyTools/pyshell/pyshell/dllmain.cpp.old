/*********************************************************************
      | credits : https://github.com/call-042PE/PyInjector |
      | modded by 0xmrpepe : https://github.com/Fadi002    |
      |                  de4py project                     |
*********************************************************************/
#include "SDK.h"
#include <Windows.h>
#include <iostream>
using namespace std;
HANDLE pipe = NULL;

bool Pyshell_GUI() {
    try
    {
        PyGILState_STATE s = PyGILState_Ensure();
        PyRun_SimpleString("import tkinter as t\ndef e():\n    c=o.get('1.0','end-1c')\n    try:exec(c)\n    except Exception as e:r.delete('1.0','end');r.insert('1.0',f'Error: {e}')\nr=t.Tk();r.title('Python shell');l=t.Label(r,text='Write python code:');l.pack(pady=10);o=t.Text(r,height=10,width=50);o.pack(pady=10);b=t.Button(r,text='Execute',command=e);b.pack();r=t.Text(r,height=5,width=50);r.pack(pady=10);r.mainloop()");
        PyGILState_Release(s);
        return true;
    }
    catch (const exception&)
    {
        return false;
    }
    
}
bool exec(char* code) {
    try {
        PyGILState_STATE s = PyGILState_Ensure();
        PyRun_SimpleString(code);
        PyGILState_Release(s);
        return true;
    }
    catch (const exception&) {
        return false;
    }
}
void unload_dll(HMODULE hModule)
{
    FreeLibraryAndExitThread(hModule, 0);
    CloseHandle(hModule);
}
void Force_crash() {
    int* ptr = new int;
    delete ptr;
    *ptr = 999940001499980000;
}
SDK sdk;
bool SendMessageToPipe(HANDLE pipe, const char* message) {
    DWORD bytesWritten;
    return WriteFile(pipe, message, strlen(message) + 1, &bytesWritten, NULL);
}
DWORD WINAPI MainThread(HMODULE hModule)
{
    string ExitHook = "import sys\nimport os\ndef _exit(*var):pass\nsetattr(sys, 'exit', _exit)\nsetattr(__builtins__, 'exit', _exit)\nsetattr(os, '_exit', _exit)\n";
    string DumpStringsHook = "\n[(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]; open(DE4PYHOOKEEEEE99_ignore, 'w').write('\\n'.join(f'{n} = {v}' for n, v in [(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]))";
    string GetFunctionsHook = "\nimport inspect as de4pyhook3_ignore; de4pyhook2_ignore = lambda de4pyhook1_ignore: hex(id(de4pyhook1_ignore.__code__.co_code)) if hasattr(de4pyhook1_ignore, '__code__') else None; [open(DE4PYHOOKEEEEE99_ignore, 'a').write(f\"{'function' if de4pyhook3_ignore.isfunction(m) else 'member'} name: {n}, address: {de4pyhook2_ignore(m)}\\n\") for n, m in de4pyhook3_ignore.getmembers(__import__('__main__'))]";
    string PYTHON_CODE_EXECUTOR = "\nexec(open(DE4PY_ignore6784878665878698698679067060,'r',encoding='utf8').read())";
    sdk.InitCPython();
    Py_SetProgramName(L"de4pyPyshell");
    PyEval_InitThreads();
    pipe = CreateNamedPipe(L"\\\\.\\pipe\\de4py",
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_WAIT,
        1,
        0,
        0,
        0,
        NULL);

    if (pipe == INVALID_HANDLE_VALUE) {
        cerr << "Error creating pipe" << endl;
        return 1;
    }

    ConnectNamedPipe(pipe, NULL);


    char buffer[1024] = { 0 };

    if (buffer != NULL)
    {
        while (true) {
            DWORD bytesRead;
            ReadFile(pipe, buffer, sizeof(buffer), &bytesRead, NULL);
            if (bytesRead > 0) {
                if (strcmp(buffer, "PyshellGUI") == 0) {
                    try
                    {
                        CreateThread(NULL, NULL, (LPTHREAD_START_ROUTINE)Pyshell_GUI, NULL, NULL, NULL);
                        SendMessageToPipe(pipe, "OK.");
                    }
                    catch (const exception& e) {
                        SendMessageToPipe(pipe, "Failed.");
                        cerr << "exception: " << e.what() << endl;
                    }

                }
                else if (strcmp(buffer, "ForceCrash") == 0) {
                    SendMessageToPipe(pipe, "OK.");
                    DisconnectNamedPipe(pipe);
                    CloseHandle(pipe);
                    Force_crash();
                }
                else if (strcmp(buffer, "DeattachDLL") == 0) {
                    SendMessageToPipe(pipe, "OK.");
                    DisconnectNamedPipe(pipe);
                    CloseHandle(pipe);
                    unload_dll(hModule);
                }
                else if (strcmp(buffer, "delExit") == 0) {
                    if (exec(const_cast<char*>(ExitHook.c_str()))) {
                        SendMessageToPipe(pipe, "OK.");
                    }
                    else {
                        SendMessageToPipe(pipe, "Failed.");
                    }
                }
                else if (string(buffer).rfind("DumpStrings", 0) == 0) {
                    std::string o = DumpStringsHook;
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        DumpStringsHook = "DE4PYHOOKEEEEE99_ignore=r'" + lol.substr(ok + 2) + "'" + DumpStringsHook;
                    }
                    if (exec(const_cast<char*>(DumpStringsHook.c_str()))) {
                        DumpStringsHook = o;
                        o = "";
                        lol = "";
                        ok = 0;
                        SendMessageToPipe(pipe, "OK.");
                    }
                    else {
                        SendMessageToPipe(pipe, "Failed.");
                    }
                }
                else if (string(buffer).rfind("GetFunctions", 0) == 0) {
                    std::string o = GetFunctionsHook;
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        GetFunctionsHook = "DE4PYHOOKEEEEE99_ignore=r'" + lol.substr(ok + 2) + "'" + GetFunctionsHook;
                    }

                    if (exec(const_cast<char*>(GetFunctionsHook.c_str()))) {
                        GetFunctionsHook = o;
                        o = "";
                        lol = "";
                        ok = 0;
                        SendMessageToPipe(pipe, "OK.");
                    }
                    else {
                        SendMessageToPipe(pipe, "Failed.");
                    }
                }
                else if (string(buffer).rfind("ExecPY", 0) == 0) {
                    std::string o = PYTHON_CODE_EXECUTOR;
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        PYTHON_CODE_EXECUTOR = "DE4PY_ignore6784878665878698698679067060=r'" + lol.substr(ok + 2) + "'" + PYTHON_CODE_EXECUTOR;
                    }

                    if (exec(const_cast<char*>(PYTHON_CODE_EXECUTOR.c_str()))) {
                        PYTHON_CODE_EXECUTOR = o;
                        o = "";
                        lol = "";
                        ok = 0;
                        SendMessageToPipe(pipe, "OK.");
                    }
                    else {
                        SendMessageToPipe(pipe, "Failed.");
                    }
                }
                else {
                    SendMessageToPipe(pipe, "WTF?");
                }
            }
        }
        DisconnectNamedPipe(pipe);
        CloseHandle(pipe);
    }
    
}

BOOL APIENTRY DllMain( HMODULE hModule,
                       DWORD  ul_reason_for_call,
                       LPVOID lpReserved
                     )
{
    switch (ul_reason_for_call)
    {
    case DLL_PROCESS_ATTACH:
        CloseHandle(CreateThread(0, 0, (LPTHREAD_START_ROUTINE)MainThread, hModule, 0, 0));
    case DLL_THREAD_ATTACH:
    case DLL_THREAD_DETACH:
    case DLL_PROCESS_DETACH:
        break;
    }
    return TRUE;
}

