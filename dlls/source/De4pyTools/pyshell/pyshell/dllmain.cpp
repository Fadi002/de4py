/*********************************************************************
      | credits : https://github.com/call-042PE/PyInjector |
      | modded by 0xmrpepe : https://github.com/Fadi002    |
      |                  de4py project                     |
*********************************************************************/
#include "SDK.h"
#include <Windows.h>
#include <iostream>
#include <detours.h>
#include <stdlib.h>
#include <sstream>
#include <codecvt>
#pragma comment(lib, "Ws2_32.lib")
//using namespace std;
HANDLE pipe = NULL;
HANDLE pipe_analyzer = NULL;

typedef struct _UNICODE_STRING {
    USHORT Length;
    USHORT MaximumLength;
    PWSTR  Buffer;
} UNICODE_STRING, * PUNICODE_STRING;

typedef struct _OBJECT_ATTRIBUTES {
    ULONG              Length;
    HANDLE             RootDirectory;
    PUNICODE_STRING    ObjectName;
    ULONG              Attributes;
    PVOID              SecurityDescriptor;
    PVOID              SecurityQualityOfService;
} OBJECT_ATTRIBUTES, *POBJECT_ATTRIBUTES;

typedef struct _IO_STATUS_BLOCK
{
    union
    {
        LONG Status;
        PVOID Pointer;
    };
    ULONG Information;
} IO_STATUS_BLOCK, * PIO_STATUS_BLOCK;

typedef struct _CLIENT_ID {
    PVOID              UniqueProcess;
    PVOID              UniqueThread;
} CLIENT_ID, * PCLIENT_ID;

typedef NTSTATUS(NTAPI* RealNtCreateFile)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES, PIO_STATUS_BLOCK, PLARGE_INTEGER, ULONG, ULONG, ULONG, ULONG, PVOID, ULONG);
typedef NTSTATUS(NTAPI* RealNtOpenProcess)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES, PCLIENT_ID);
typedef NTSTATUS(NTAPI* RealNtWriteVirtualMemory)(HANDLE, PVOID, LPCVOID, SIZE_T, PSIZE_T);
typedef NTSTATUS(NTAPI* RealNtReadVirtualMemory)(HANDLE, PVOID, PVOID, ULONG, PULONG);
typedef NTSTATUS(NTAPI* RealNtTerminateProcess)(HANDLE, NTSTATUS);
typedef SOCKET(WINAPI* RealSocket)(int, int, int);
typedef int (WINAPI* RealSend)(SOCKET, const char*, int, int);
typedef int (WINAPI* RealRecv)(SOCKET, char*, int, int);

bool Pyshell_GUI() {
    try
    {
        PyGILState_STATE s = PyGILState_Ensure();
        PyRun_SimpleString("import tkinter as t\ndef e():\n    c=o.get('1.0','end-1c')\n    try:exec(c)\n    except Exception as e:r.delete('1.0','end');r.insert('1.0',f'Error: {e}')\nr=t.Tk();r.title('Python shell');l=t.Label(r,text='Write python code:');l.pack(pady=10);o=t.Text(r,height=10,width=50);o.pack(pady=10);b=t.Button(r,text='Execute',command=e);b.pack();r=t.Text(r,height=5,width=50);r.pack(pady=10);r.mainloop()");
        PyGILState_Release(s);
        return true;
    }
    catch (const std::exception&)
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
    catch (const std::exception&) {
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
HANDLE PipeMutex = CreateMutex(NULL, FALSE, NULL);
HANDLE PipeMutex2 = CreateMutex(NULL, FALSE, NULL);
bool SendMessageToPipe(HANDLE pipe, const char* message) {
    WaitForSingleObject(PipeMutex, INFINITE);
    DWORD bytesWritten = 0;
    BOOL Status = WriteFile(pipe, message, strlen(message) + 1, &bytesWritten, NULL);
    ReleaseMutex(PipeMutex);
    return Status;
}

bool SendMessageToPipe(HANDLE pipe, const wchar_t* message) {
    WaitForSingleObject(PipeMutex2, INFINITE);
    DWORD bytesWritten = 0;
    std::wstring_convert<std::codecvt_utf8<wchar_t>> Converter;
    std::string message2 = Converter.to_bytes(message);
    BOOL Status = WriteFile(pipe, message2.c_str(), message2.size() + 1, &bytesWritten, NULL);
    ReleaseMutex(PipeMutex2);
    return Status;
}

RealNtCreateFile OriginalNtCreateFile = nullptr;
HANDLE NtCreateFileMutex = CreateMutex(NULL, FALSE, NULL);

NTSTATUS NTAPI HookedNtCreateFile(PHANDLE FileHandle, ACCESS_MASK DesiredAccess, POBJECT_ATTRIBUTES ObjectAttributes, PIO_STATUS_BLOCK IoStatusBlock, PLARGE_INTEGER AllocationSize, ULONG FileAttributes, ULONG ShareAccess, ULONG CreateDisposition, ULONG CreateOptions, PVOID EaBuffer, ULONG EaLength)
{
    WaitForSingleObject(NtCreateFileMutex, INFINITE);
    std::wstring szFileName(ObjectAttributes->ObjectName->Buffer, ObjectAttributes->ObjectName->Length / sizeof(wchar_t));
    NTSTATUS Status = OriginalNtCreateFile(FileHandle, DesiredAccess, ObjectAttributes, IoStatusBlock, AllocationSize, FileAttributes, ShareAccess, CreateDisposition, CreateOptions, EaBuffer, EaLength);
    if (Status == 0)
    {
        std::wstring FileName(L"File Handle Opened: ");
        FileName.append(szFileName.c_str());
        SendMessageToPipe(pipe_analyzer, FileName.c_str());
    }
    ReleaseMutex(NtCreateFileMutex);
    return Status;
}

BOOL IsHookedFileMon = false;
void MonitorFiles(BOOL Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(PVOID&)OriginalNtCreateFile, HookedNtCreateFile);
        DetourTransactionCommit();
        IsHookedFileMon = FALSE;
    }
    else
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        OriginalNtCreateFile = reinterpret_cast<RealNtCreateFile>(DetourFindFunction("ntdll.dll", "NtCreateFile"));
        DetourAttach(&(LPVOID&)OriginalNtCreateFile, HookedNtCreateFile);
        DetourTransactionCommit();
        IsHookedFileMon = TRUE;
    }
}

RealNtOpenProcess OriginalNtOpenProcess = nullptr;
HANDLE NtOpenProcessMutex = CreateMutex(NULL, FALSE, NULL);

NTSTATUS NTAPI HookedNtOpenProcess(PHANDLE ProcessHandle, ACCESS_MASK DesiredAccess, POBJECT_ATTRIBUTES ObjectAttributes, PCLIENT_ID ClientId)
{
    WaitForSingleObject(NtOpenProcessMutex, INFINITE);
    NTSTATUS Status = OriginalNtOpenProcess(ProcessHandle, DesiredAccess, ObjectAttributes, ClientId);
    DWORD PID = (DWORD)ClientId->UniqueProcess;
    std::string Process("Process handle opened to pid: ");
    Process.append(std::to_string(PID).c_str());
    SendMessageToPipe(pipe_analyzer, Process.c_str());
    ReleaseMutex(NtOpenProcessMutex);
    return Status;
}

RealNtWriteVirtualMemory OriginalNtWriteVirtualMemory = nullptr;
HANDLE NtWriteVirtualMemoryMutex = CreateMutex(NULL, FALSE, NULL);
NTSTATUS NTAPI HookedNtWriteVirtualMemory(HANDLE ProcessHandle, PVOID BaseAddress, LPCVOID Buffer, SIZE_T BufferSize, PSIZE_T NumberOfBytesWritten)
{
    WaitForSingleObject(NtWriteVirtualMemoryMutex, INFINITE);
    NTSTATUS Status = 0;
    DWORD PID = GetProcessId(ProcessHandle);
    if (PID != GetCurrentProcessId())
    {
        Status = OriginalNtWriteVirtualMemory(ProcessHandle, BaseAddress, Buffer, BufferSize, NumberOfBytesWritten);
        if (Status == 0)
        {
            std::string Process("The Process wrote to the process memory of: ");
            Process.append(std::to_string(PID).c_str());
            SendMessageToPipe(pipe_analyzer, Process.c_str());
        }
        ReleaseMutex(NtWriteVirtualMemoryMutex);
        return Status;
    }
    else
    {
        Status = OriginalNtWriteVirtualMemory(ProcessHandle, BaseAddress, Buffer, BufferSize, NumberOfBytesWritten);
        ReleaseMutex(NtWriteVirtualMemoryMutex);
        return Status;
    }
}

RealNtReadVirtualMemory OriginalNtReadVirtualMemory = nullptr;
HANDLE NtReadVirtualMemoryMutex = CreateMutex(NULL, FALSE, NULL);
NTSTATUS NTAPI HookedNtReadVirtualMemory(HANDLE ProcessHandle, PVOID BaseAddress, PVOID Buffer, ULONG NumberOfBytesToRead, PULONG NumberOfBytesRead)
{
    WaitForSingleObject(NtReadVirtualMemoryMutex, INFINITE);
    NTSTATUS Status = 0;
    DWORD PID = GetProcessId(ProcessHandle);
    if (PID != GetCurrentProcessId())
    {
        Status = OriginalNtReadVirtualMemory(ProcessHandle, BaseAddress, Buffer, NumberOfBytesToRead, NumberOfBytesRead);
        if (Status == 0)
        {
            std::string Process("The Process readed the process memory of: ");
            Process.append(std::to_string(PID).c_str());
            SendMessageToPipe(pipe_analyzer, Process.c_str());
        }
        ReleaseMutex(NtReadVirtualMemoryMutex);
        return Status;
    }
    else
    {
        Status = OriginalNtReadVirtualMemory(ProcessHandle, BaseAddress, Buffer, NumberOfBytesToRead, NumberOfBytesRead);
        ReleaseMutex(NtReadVirtualMemoryMutex);
        return Status;
    }
}

RealNtTerminateProcess OriginalNtTerminateProcess = nullptr;
HANDLE NtTerminateProcessMutex = CreateMutex(NULL, FALSE, NULL);

NTSTATUS NTAPI HookedNtTerminateProcess(HANDLE hProcess, NTSTATUS ExitCode)
{
    WaitForSingleObject(NtTerminateProcessMutex, INFINITE);
    NTSTATUS Status = 0;
    DWORD PID = GetProcessId(hProcess);
    if (PID != GetCurrentProcessId())
    {
        Status = OriginalNtTerminateProcess(hProcess, ExitCode);
        if (Status == 0)
        {
            std::string Process("The Process terminated the process with the pid: ");
            Process.append(std::to_string(PID).c_str());
            SendMessageToPipe(pipe_analyzer, Process.c_str());
        }
        ReleaseMutex(NtTerminateProcessMutex);
        return Status;
    }
    else
    {
        Status = OriginalNtTerminateProcess(hProcess, ExitCode);
        ReleaseMutex(NtTerminateProcessMutex);
        return Status;
    }
}

BOOL IsHookedProcessMon = false;
void MonitorProcessesHandles(BOOL Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(PVOID&)OriginalNtOpenProcess, HookedNtOpenProcess);
        DetourDetach(&(PVOID&)OriginalNtWriteVirtualMemory, HookedNtWriteVirtualMemory);
        DetourDetach(&(PVOID&)OriginalNtReadVirtualMemory, HookedNtReadVirtualMemory);
        DetourDetach(&(PVOID&)OriginalNtTerminateProcess, HookedNtTerminateProcess);
        DetourTransactionCommit();
        IsHookedProcessMon = false;
    }
    else
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        OriginalNtOpenProcess = reinterpret_cast<RealNtOpenProcess>(DetourFindFunction("ntdll.dll", "NtOpenProcess"));
        DetourAttach(&(LPVOID&)OriginalNtOpenProcess, HookedNtOpenProcess);
        OriginalNtWriteVirtualMemory = reinterpret_cast<RealNtWriteVirtualMemory>(DetourFindFunction("ntdll.dll", "NtWriteVirtualMemory"));
        DetourAttach(&(LPVOID&)OriginalNtWriteVirtualMemory, HookedNtWriteVirtualMemory);
        OriginalNtReadVirtualMemory = reinterpret_cast<RealNtReadVirtualMemory>(DetourFindFunction("ntdll.dll", "NtReadVirtualMemory"));
        DetourAttach(&(LPVOID&)OriginalNtReadVirtualMemory, HookedNtReadVirtualMemory);
        OriginalNtTerminateProcess = reinterpret_cast<RealNtTerminateProcess>(DetourFindFunction("ntdll.dll", "NtTerminateProcess"));
        DetourAttach(&(LPVOID&)OriginalNtTerminateProcess, HookedNtTerminateProcess);
        DetourTransactionCommit();
        IsHookedProcessMon = true;
    }
}

RealSocket OriginalSocket = nullptr;
RealSend OriginalSend = nullptr;
RealRecv OriginalRecv = nullptr;

HANDLE SocketMutex = CreateMutex(NULL, FALSE, NULL);
SOCKET WINAPI HookedSocket(int af, int type, int protocol)
{
    WaitForSingleObject(SocketMutex, INFINITE);
    SendMessageToPipe(pipe_analyzer, "The Process have created a socket...");
    SOCKET sock = OriginalSocket(af, type, protocol);
    ReleaseMutex(SocketMutex);
    return sock;
}

HANDLE SendMutex = CreateMutex(NULL, FALSE, NULL);
int WINAPI HookedSend(SOCKET sock, const char* buf, int len, int flags)
{
    WaitForSingleObject(SendMutex, INFINITE);
    int Status = OriginalSend(sock, buf, len, flags);
    if (Status != SOCKET_ERROR)
    {
        sockaddr_in destAddress;
        int destAddrSize = sizeof(destAddress);
        getpeername(sock, (sockaddr*)&destAddress, &destAddrSize);
        char* Address = inet_ntoa(destAddress.sin_addr);
        std::string Info("The Process successfully sent \"");
        Info.append(std::to_string(Status).c_str());
        Info.append("\" bytes of data to: ");
        Info.append(Address);
        SendMessageToPipe(pipe_analyzer, Info.c_str());
    }
    else
    {
        std::string Info("The process tried to send data to an ip address but failed with the error code: ");
        Info.append(std::to_string(GetLastError()).c_str());
        SendMessageToPipe(pipe_analyzer, Info.c_str());
    }
    ReleaseMutex(SendMutex);
    return Status;
}

HANDLE RecvMutex = CreateMutex(NULL, FALSE, NULL);
int WINAPI HookedRecv(SOCKET sock, char* buf, int len, int flags)
{
    WaitForSingleObject(RecvMutex, INFINITE);
    int Status = OriginalRecv(sock, buf, len, flags);
    if (Status != SOCKET_ERROR)
    {
        sockaddr_in destAddress;
        int destAddrSize = sizeof(destAddress);
        getpeername(sock, (sockaddr*)&destAddress, &destAddrSize);
        char* Address = inet_ntoa(destAddress.sin_addr);
        std::string Info("The Process successfully recieved \"");
        Info.append(std::to_string(Status).c_str());
        Info.append("\" bytes of data from: ");
        Info.append(Address);
        SendMessageToPipe(pipe_analyzer, Info.c_str());
    }
    else
    {
        std::string Info("The process tried to receive data from an ip address but failed with the error code: ");
        Info.append(std::to_string(GetLastError()).c_str());
        SendMessageToPipe(pipe_analyzer, Info.c_str());
    }
    ReleaseMutex(RecvMutex);
    return Status;
}

BOOL IsHookedConnectionsMon = false;
void MonitorConnections(BOOL Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(LPVOID&)OriginalSocket, HookedSocket);
        DetourDetach(&(LPVOID&)OriginalSend, HookedSend);
        DetourDetach(&(LPVOID&)OriginalRecv, HookedRecv);
        DetourTransactionCommit();
        IsHookedConnectionsMon = false;
    }
    else
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        OriginalSocket = reinterpret_cast<RealSocket>(DetourFindFunction("Ws2_32.dll", "socket"));
        DetourAttach(&(LPVOID&)OriginalSocket, HookedSocket);
        OriginalSend = reinterpret_cast<RealSend>(DetourFindFunction("Ws2_32.dll", "send"));
        DetourAttach(&(LPVOID&)OriginalSend, HookedSend);
        OriginalRecv = reinterpret_cast<RealRecv>(DetourFindFunction("Ws2_32.dll", "recv"));
        DetourAttach(&(LPVOID&)OriginalRecv, HookedRecv);
        DetourTransactionCommit();
        IsHookedConnectionsMon = true;
    }
}

DWORD WINAPI MainThread(HMODULE hModule)
{
    std::string ExitHook = "import sys\nimport os\ndef _exit(*var):pass\nsetattr(sys, 'exit', _exit)\nsetattr(__builtins__, 'exit', _exit)\nsetattr(os, '_exit', _exit)\n";
    std::string DumpStringsHook = "\n[(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]; open(DE4PYHOOKEEEEE99_ignore, 'w').write('\\n'.join(f'{n} = {v}' for n, v in [(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]))";
    std::string GetFunctionsHook = "\nimport inspect as de4pyhook3_ignore; de4pyhook2_ignore = lambda de4pyhook1_ignore: hex(id(de4pyhook1_ignore.__code__.co_code)) if hasattr(de4pyhook1_ignore, '__code__') else None; [open(DE4PYHOOKEEEEE99_ignore, 'a').write(f\"{'function' if de4pyhook3_ignore.isfunction(m) else 'member'} name: {n}, address: {de4pyhook2_ignore(m)}\\n\") for n, m in de4pyhook3_ignore.getmembers(__import__('__main__'))]";
    std::string PYTHON_CODE_EXECUTOR = "\nexec(open(DE4PY_ignore6784878665878698698679067060,'r',encoding='utf8').read())";
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
        std::cerr << "Error creating pipe" << std::endl;
        return 1;
    }

    ConnectNamedPipe(pipe, NULL);


    char buffer[1024] = { 0 };

    if (buffer != NULL)
    {
        while (true) {
            memset(buffer, 0, sizeof(buffer));
            DWORD bytesRead;
            ReadFile(pipe, buffer, sizeof(buffer), &bytesRead, NULL);
            if (bytesRead > 0) {
                if (strcmp(buffer, "PyshellGUI") == 0) {
                    try
                    {
                        CreateThread(NULL, NULL, (LPTHREAD_START_ROUTINE)Pyshell_GUI, NULL, NULL, NULL);
                        SendMessageToPipe(pipe, "OK.");
                    }
                    catch (const std::exception& e) {
                        SendMessageToPipe(pipe, "Failed.");
                        std::cerr << "exception: " << e.what() << std::endl;
                    }
                }
                else if (strcmp(buffer, "ForceCrash") == 0) {
                    SendMessageToPipe(pipe, "OK.");
                    DisconnectNamedPipe(pipe);
                    CloseHandle(pipe);
                    Force_crash();
                }
                else if (strcmp(buffer, "GetAnalyzerHandle") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        SendMessageToPipe(pipe, "Analyzation pipe already exists.");
                    }
                    else
                    {
                        pipe_analyzer = CreateNamedPipe(L"\\\\.\\pipe\\de4py_analyzer",
                            PIPE_ACCESS_DUPLEX,
                            PIPE_TYPE_BYTE | PIPE_WAIT,
                            1,
                            0,
                            0,
                            0,
                            NULL);
                        if (pipe_analyzer != INVALID_HANDLE_VALUE)
                        {
                            SendMessageToPipe(pipe, "created analyzation pipe.");
                        }
                        else
                        {
                            SendMessageToPipe(pipe, "failed to create the pipe...");
                        }
                    }
                }
                else if (strcmp(buffer, "MonitorFiles") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (IsHookedFileMon)
                        {
                            SendMessageToPipe(pipe, "already monitoring.");
                        }
                        else
                        {
                            MonitorFiles(false);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "UnMonitorFiles") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsHookedFileMon)
                        {
                            SendMessageToPipe(pipe, "not monitoring in the first place.");
                        }
                        else
                        {
                            MonitorFiles(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "MonitorProcesses") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (IsHookedProcessMon)
                        {
                            SendMessageToPipe(pipe, "already monitoring.");
                        }
                        else
                        {
                            MonitorProcessesHandles(false);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "UnMonitorProcesses") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsHookedProcessMon)
                        {
                            SendMessageToPipe(pipe, "not monitoring in the first place.");
                        }
                        else
                        {
                            MonitorProcessesHandles(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "MonitorConnections") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (IsHookedConnectionsMon)
                        {
                            SendMessageToPipe(pipe, "already monitoring.");
                        }
                        else
                        {
                            MonitorConnections(false);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "UnMonitorConnections") == 0) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsHookedConnectionsMon)
                        {
                            SendMessageToPipe(pipe, "not monitoring in the first place.");
                        }
                        else
                        {
                            MonitorConnections(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (strcmp(buffer, "DeattachDLL") == 0){
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsHookedConnectionsMon)
                        {
                            SendMessageToPipe(pipe, "not monitoring in the first place.");
                        }
                        else
                        {
                            MonitorConnections(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
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
                else if (std::string(buffer).rfind("DumpStrings", 0) == 0) {
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
                else if (std::string(buffer).rfind("GetFunctions", 0) == 0) {
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
                else if (std::string(buffer).rfind("ExecPY", 0) == 0) {
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