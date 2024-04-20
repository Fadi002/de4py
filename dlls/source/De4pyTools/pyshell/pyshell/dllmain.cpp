/*********************************************************************
      | credits : https://github.com/call-042PE/PyInjector |
      | modded by 0xmrpepe : https://github.com/Fadi002    |
      |                  de4py project                     |
*********************************************************************/
#include "SDK.h"
#include <iostream>
#include <Windows.h>
#include <detours.h>
#include <stdlib.h>
#include <sstream>
#include <codecvt>
#include <regex>
#define SECURITY_WIN32
#include <security.h>
#include <Sspi.h>
#include <Psapi.h>
#include <string>
#include <random>
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

typedef struct
{
    int type;
} BIO_METHOD;

typedef struct bio_st
{
    BIO_METHOD* method;
    void* callback;
    char* cb_arg;
    int init;
    int shutdown;
    int flags;
    int retry_reason;
    int num;
    void* ptr;
    struct bio_st* next_bio;
    struct bio_st* prev_bio;
    int refs;
    unsigned long num_read;
    unsigned long num_write;
} BIO;

typedef struct
{
    int version;
    int type;
    void* method;

    BIO* rbio;
    BIO* wbio;
    BIO* bbio;

    int rwstate;
    int in_handshake;
    void* handshake_func;

    int server;
    int new_session;
    int quiet_shutdown;
    int shutdown;
    int state;
    int rstate;

    void* init_buf;
    void* init_msg;
    int   init_num;
    int   init_off;

    unsigned char* packet;
    unsigned int   packet_length;

} SSL;

typedef NTSTATUS(NTAPI* RealNtCreateFile)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES, PIO_STATUS_BLOCK, PLARGE_INTEGER, ULONG, ULONG, ULONG, ULONG, PVOID, ULONG);
typedef NTSTATUS(NTAPI* RealNtOpenProcess)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES, PCLIENT_ID);
typedef NTSTATUS(NTAPI* RealNtWriteVirtualMemory)(HANDLE, PVOID, LPCVOID, SIZE_T, PSIZE_T);
typedef NTSTATUS(NTAPI* RealNtReadVirtualMemory)(HANDLE, PVOID, PVOID, ULONG, PULONG);
typedef NTSTATUS(NTAPI* RealNtTerminateProcess)(HANDLE, NTSTATUS);
typedef HHOOK(WINAPI* RealSetWindowsHookExAW)(int, HOOKPROC, HINSTANCE, DWORD);
typedef SOCKET(WINAPI* RealSocket)(int, int, int);
typedef int (WINAPI* RealSend)(SOCKET, const char*, int, int);
typedef int (WINAPI* RealRecv)(SOCKET, char*, int, int);
typedef int(__cdecl* RealSSL_read)(SSL*, void*, size_t);
typedef int(__cdecl* RealSSL_write)(SSL*, const void*, size_t);
typedef int(__cdecl* RealSSL_read_ex)(SSL*, void*, size_t, size_t*);
typedef int(__cdecl* RealSSL_write_ex)(SSL*, const void*, size_t, size_t*);
typedef void*(__cdecl* RealPyEval_EvalCode)(void*, void*, void*);
typedef void(__cdecl* PyMarshal_WriteObjectToFile)(void*, FILE*, int);

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
    std::string message_modified(message);
    message_modified.append("\n");
    BOOL Status = WriteFile(pipe, message_modified.c_str(), message_modified.size() + 1, &bytesWritten, NULL);
    ReleaseMutex(PipeMutex);
    return Status;
}

bool SendMessageToPipe(HANDLE pipe, const wchar_t* message) {
    WaitForSingleObject(PipeMutex2, INFINITE);
    DWORD bytesWritten = 0;
    std::wstring_convert<std::codecvt_utf8<wchar_t>> Converter;
    std::string message2 = Converter.to_bytes(message).append("\n");
    BOOL Status = WriteFile(pipe, message2.c_str(), message2.size() + 1, &bytesWritten, NULL);
    ReleaseMutex(PipeMutex2);
    return Status;
}

RealNtCreateFile OriginalNtCreateFile = nullptr;
HANDLE NtCreateFileMutex = CreateMutex(NULL, FALSE, NULL);

void AppendString(wchar_t* string1, const wchar_t* string2)
{
    if (string1 == NULL || string2 == NULL) {
        return;
    }
    size_t size1 = wcslen(string1);
    wcscpy_s(string1 + size1, wcslen(string1) - 1, string2);
}

NTSTATUS NTAPI HookedNtCreateFile(PHANDLE FileHandle, ACCESS_MASK DesiredAccess, POBJECT_ATTRIBUTES ObjectAttributes, PIO_STATUS_BLOCK IoStatusBlock, PLARGE_INTEGER AllocationSize, ULONG FileAttributes, ULONG ShareAccess, ULONG CreateDisposition, ULONG CreateOptions, PVOID EaBuffer, ULONG EaLength)
{
    WaitForSingleObject(NtCreateFileMutex, INFINITE);
    std::wstring szFileName(ObjectAttributes->ObjectName->Buffer, ObjectAttributes->ObjectName->Length / sizeof(wchar_t));
    NTSTATUS Status = OriginalNtCreateFile(FileHandle, DesiredAccess, ObjectAttributes, IoStatusBlock, AllocationSize, FileAttributes, ShareAccess, CreateDisposition, CreateOptions, EaBuffer, EaLength);
    if (Status == 0)
    {
        wchar_t Message[256];
        DWORD LastError = GetLastError();
        if (CreateDisposition == CREATE_ALWAYS)
        {
            if (LastError == ERROR_ALREADY_EXISTS)
            {
                AppendString(Message, L"File Handle Opened: ");
            }
            else
            {
                AppendString(Message, L"File Created: ");
            }
        }
        else if(CreateDisposition == CREATE_NEW)
        {
            AppendString(Message, L"File Created: ");
        }
        else
        {
            AppendString(Message, L"File Handle Opened: ");
        }
        std::wstring FileName(Message);
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
    if (PID != GetCurrentProcessId() && PID != 0)
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

RealSetWindowsHookExAW OriginalSetWindowsHookExAW = nullptr;
HANDLE SetWindowsHookExAWMutex = CreateMutex(NULL, FALSE, NULL);
HHOOK WINAPI HookedSetWindowsHookExAW(int idHook, HOOKPROC lpfn, HINSTANCE hMod, DWORD dwThreadId)
{
    WaitForSingleObject(SetWindowsHookExAWMutex, INFINITE);
    HHOOK Status = OriginalSetWindowsHookExAW(idHook, lpfn, hMod, dwThreadId);
    if (dwThreadId == 0 && Status != NULL)
    {
        if (idHook & WH_KEYBOARD || idHook & WH_KEYBOARD_LL)
        {
            SendMessageToPipe(pipe_analyzer, "The Process installed a global keyboard hook which can be used to monitor keystrokes.");
        }

        if (idHook & WH_MOUSE || idHook & WH_MOUSE_LL)
        {
            SendMessageToPipe(pipe_analyzer, "The Process installed a global mouse hook.");
        }
    }
    ReleaseMutex(SetWindowsHookExAWMutex);
    return Status;
}

BOOL IsHookedProcessMon = false;
void MonitorGeneralProcessBehavior(BOOL Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(PVOID&)OriginalNtOpenProcess, HookedNtOpenProcess);
        DetourDetach(&(PVOID&)OriginalNtWriteVirtualMemory, HookedNtWriteVirtualMemory);
        DetourDetach(&(PVOID&)OriginalNtReadVirtualMemory, HookedNtReadVirtualMemory);
        DetourDetach(&(PVOID&)OriginalNtTerminateProcess, HookedNtTerminateProcess);
        DetourDetach(&(PVOID&)OriginalSetWindowsHookExAW, HookedSetWindowsHookExAW);
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
        OriginalSetWindowsHookExAW = reinterpret_cast<RealSetWindowsHookExAW>(DetourFindFunction("user32.dll", "SetWindowsHookExAW"));
        DetourAttach(&(LPVOID&)OriginalSetWindowsHookExAW, HookedSetWindowsHookExAW);
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

BOOL DumpContent = FALSE;
char DumpPath[MAX_PATH + 1];

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
        Info.append(std::to_string(Status));
        Info.append("\" bytes of data to: ");
        Info.append(Address);
        SendMessageToPipe(pipe_analyzer, Info.c_str());
        if (DumpContent && DumpPath != NULL)
        {
            HANDLE File = CreateFileA(DumpPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
            if (File != INVALID_HANDLE_VALUE)
            {
                SetFilePointer(File, 0, NULL, FILE_END);
                std::string Buffer(buf, len);
                Buffer.append("\n");
                DWORD Written = 0;
                WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL);
                CloseHandle(File);
            }
        }
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
        std::string Info("The Process successfully sent \"");
        Info.append(std::to_string(Status).c_str());
        Info.append("\" bytes of data to: ");
        Info.append(Address);
        SendMessageToPipe(pipe_analyzer, Info.c_str());
        if (DumpContent && DumpPath != NULL)
        {
            HANDLE File = CreateFileA(DumpPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
            if (File != INVALID_HANDLE_VALUE)
            {
                SetFilePointer(File, 0, NULL, FILE_END);
                std::string Buffer(buf, len);
                Buffer.append("\n");
                DWORD Written = 0;
                WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL);
                CloseHandle(File);
            }
        }
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

char DumpSSLPath[MAX_PATH + 1];
RealSSL_read OriginalSSL_read = nullptr;
RealSSL_write OriginalSSL_write = nullptr;
RealSSL_read_ex OriginalSSL_read_ex = nullptr;
RealSSL_write_ex OriginalSSL_write_ex = nullptr;

HANDLE SSL_read_exMutex = CreateMutex(NULL, FALSE, NULL);
int HookedSSL_read_ex(SSL* ssl, void* buf, size_t num, size_t* readbytes)
{
    WaitForSingleObject(SSL_read_exMutex, INFINITE);
    if (DumpSSLPath != NULL)
    {
        HANDLE File = CreateFileA(DumpSSLPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (File != INVALID_HANDLE_VALUE)
        {
            SetFilePointer(File, 0, NULL, FILE_END);
            std::string Buffer(static_cast<char*>(buf), num);
            Buffer.append("\n");
            DWORD Written = 0;
            if (!WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL))
                printf("Error: %i", GetLastError());
            CloseHandle(File);
        }
        else
        {
            printf("Error: %i", GetLastError());
        }
    }
    int value = OriginalSSL_read_ex(ssl, buf, num, readbytes);
    ReleaseMutex(SSL_read_exMutex);
    return value;
}

HANDLE SSL_write_exMutex = CreateMutex(NULL, FALSE, NULL);
int HookedSSL_write_ex(SSL* s, const void* buf, size_t num, size_t* written)
{
    WaitForSingleObject(SSL_write_exMutex, INFINITE);
    if (DumpSSLPath != NULL)
    {
        HANDLE File = CreateFileA(DumpSSLPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (File != INVALID_HANDLE_VALUE)
        {
            SetFilePointer(File, 0, NULL, FILE_END);
            std::string Buffer(static_cast<const char*>(buf), num);
            Buffer.append("\n");
            DWORD Written = 0;
            if(!WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL))
                printf("Error: %i", GetLastError());
            CloseHandle(File);
        }
        else
        {
            printf("Error: %i", GetLastError());
        }
    }
    int value = OriginalSSL_write_ex(s, buf, num, written);
    ReleaseMutex(SSL_write_exMutex);
    return value;
}

HANDLE SSL_readMutex = CreateMutex(NULL, FALSE, NULL);
int HookedSSL_read(SSL* ssl, void* buf, size_t num)
{
    WaitForSingleObject(SSL_readMutex, INFINITE);
    if (DumpSSLPath != NULL)
    {
        HANDLE File = CreateFileA(DumpSSLPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (File != INVALID_HANDLE_VALUE)
        {
            SetFilePointer(File, 0, NULL, FILE_END);
            std::string Buffer(static_cast<char*>(buf), num);
            Buffer.append("\n");
            DWORD Written = 0;
            if (!WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL))
                printf("Error: %i", GetLastError());
            CloseHandle(File);
        }
        else
        {
            printf("Error: %i", GetLastError());
        }
    }
    int value = OriginalSSL_read(ssl, buf, num);
    ReleaseMutex(SSL_readMutex);
    return value;
}

HANDLE SSL_writeMutex = CreateMutex(NULL, FALSE, NULL);
int HookedSSL_write(SSL* s, const void* buf, size_t num)
{
    WaitForSingleObject(SSL_writeMutex, INFINITE);
    if (DumpSSLPath != NULL)
    {
        HANDLE File = CreateFileA(DumpSSLPath, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (File != INVALID_HANDLE_VALUE)
        {
            SetFilePointer(File, 0, NULL, FILE_END);
            std::string Buffer(static_cast<const char*>(buf), num);
            Buffer.append("\n");
            DWORD Written = 0;
            if (!WriteFile(File, Buffer.c_str(), Buffer.size(), &Written, NULL))
                printf("Error: %i", GetLastError());
            CloseHandle(File);
        }
        else
        {
            printf("Error: %i", GetLastError());
        }
    }
    int value = OriginalSSL_write(s, buf, num);
    ReleaseMutex(SSL_writeMutex);
    return value;
}

HMODULE GetPythonDll()
{
    HANDLE hProcess = GetCurrentProcess();
    HMODULE hModules[1024];
    DWORD cbNeeded;
    HMODULE Python = NULL;
    if (EnumProcessModules(hProcess, hModules, sizeof(hModules), &cbNeeded))
    {
        for (DWORD i = 0; i < (cbNeeded / sizeof(HMODULE)); i++) {
            char szModule[MAX_PATH];
            if (GetModuleFileNameExA(hProcess, hModules[i], szModule, sizeof(szModule) / sizeof(char))) {
                if (strstr(szModule, "python3") != NULL) {
                    Python = hModules[i];
                    break;
                }
            }
        }
    }
    CloseHandle(hProcess);
    return Python;
}

HMODULE GetOpenSSL()
{
    HANDLE hProcess = GetCurrentProcess();
    HMODULE hModules[1024];
    DWORD cbNeeded;
    HMODULE Python = NULL;
    if (EnumProcessModules(hProcess, hModules, sizeof(hModules), &cbNeeded))
    {
        for (DWORD i = 0; i < (cbNeeded / sizeof(HMODULE)); i++) {
            char szModule[MAX_PATH];
            if (GetModuleFileNameExA(hProcess, hModules[i], szModule, sizeof(szModule) / sizeof(char))) {
                if (strstr(szModule, "libssl") != NULL) {
                    Python = hModules[i];
                    break;
                }
            }
        }
    }
    CloseHandle(hProcess);
    return Python;
}

BOOL IsDumping = FALSE;
BOOL DumpSSL(bool Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(LPVOID&)OriginalSSL_read_ex, HookedSSL_read_ex);
        DetourDetach(&(LPVOID&)OriginalSSL_write_ex, HookedSSL_write_ex);
        DetourTransactionCommit();
        IsDumping = false;
    }
    else
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        HMODULE hModule = GetOpenSSL();
        PBYTE Real = (PBYTE)GetProcAddress(hModule, "SSL_read_ex");
        if (Real[0] == 0xE9) {
            int offset = *(int*)(Real + 1);
            void* realFunction = (void*)(Real + 5 + offset);
            OriginalSSL_read_ex = (RealSSL_read_ex)realFunction;
        }
        else
        {
            OriginalSSL_read_ex = reinterpret_cast<RealSSL_read_ex>(DetourFindFunction("libssl-1_1.dll", "SSL_read_ex"));
        }
        DetourAttach(&(LPVOID&)OriginalSSL_read_ex, HookedSSL_read_ex);
        PBYTE Real2 = (PBYTE)GetProcAddress(hModule, "SSL_write_ex");
        if (Real2[0] == 0xE9) {
            int offset = *(int*)(Real2 + 1);
            void* realFunction = (void*)(Real2 + 5 + offset);
            OriginalSSL_write_ex = (RealSSL_write_ex)realFunction;
        }
        else
        {
            OriginalSSL_write_ex = reinterpret_cast<RealSSL_write_ex>(DetourFindFunction("libssl-1_1.dll", "SSL_write_ex"));
        }
        DetourAttach(&(LPVOID&)OriginalSSL_write_ex, HookedSSL_write_ex);
        PBYTE Real3 = (PBYTE)GetProcAddress(hModule, "SSL_read");
        if (Real3[0] == 0xE9) {
            int offset = *(int*)(Real3 + 1);
            void* realFunction = (void*)(Real3 + 5 + offset);
            OriginalSSL_read = (RealSSL_read)realFunction;
        }
        else
        {
            OriginalSSL_read = reinterpret_cast<RealSSL_read>(DetourFindFunction("libssl-1_1.dll", "SSL_read"));
        }
        DetourAttach(&(LPVOID&)OriginalSSL_read, HookedSSL_read);
        PBYTE Real4 = (PBYTE)GetProcAddress(hModule, "SSL_write");
        if (Real4[0] == 0xE9) {
            int offset = *(int*)(Real4 + 1);
            void* realFunction = (void*)(Real4 + 5 + offset);
            OriginalSSL_write = (RealSSL_write)realFunction;
        }
        else
        {
            OriginalSSL_write = reinterpret_cast<RealSSL_write>(DetourFindFunction("libssl-1_1.dll", "SSL_write"));
        }
        DetourAttach(&(LPVOID&)OriginalSSL_write, HookedSSL_write);
        if (DetourTransactionCommit() != NO_ERROR)
            return false;
        IsDumping = true;
        return true;
    }
}

PyMarshal_WriteObjectToFile WriteObject = NULL;
RealPyEval_EvalCode OriginalPyEval_EvalCode = nullptr;
char PyDumpPath[MAX_PATH + 1];

std::string gen_pyc_file_name() {
    const std::string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, alphabet.size() - 1);
    std::string filename = "pdump-";
    for (int i = 0; i < 7; ++i) {
        filename += alphabet[dis(gen)];
    }
    filename += ".pyc";
    return filename;
}


HANDLE EvalMutex = CreateMutex(NULL, FALSE, NULL);
void* HookedPyEval_EvalCode(void* co, void* globals, void* locals)
{
    WaitForSingleObject(EvalMutex, INFINITE);
    FILE* Stream = NULL;
    std::string pydumpdir = PyDumpPath;
    std::string filename = pydumpdir + "\\" + gen_pyc_file_name();
    if (fopen_s(&Stream, filename.c_str(), "wb") == 0)
    {
        WriteObject(co, Stream, 4);
        fclose(Stream);
    }
    ReleaseMutex(EvalMutex);
    return OriginalPyEval_EvalCode(co, globals, locals);
}

BOOL IsHookedPy = false;
void DumpPythonCode(BOOL Unhook)
{
    if (Unhook)
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        DetourDetach(&(LPVOID&)OriginalPyEval_EvalCode, HookedPyEval_EvalCode);
        DetourTransactionCommit();
        IsHookedPy = false;
    }
    else
    {
        DetourTransactionBegin();
        DetourUpdateThread(GetCurrentThread());
        OriginalPyEval_EvalCode = (RealPyEval_EvalCode)GetProcAddress(GetPythonDll(), "PyEval_EvalCode");
        DetourAttach(&(LPVOID&)OriginalPyEval_EvalCode, HookedPyEval_EvalCode);
    }
        DetourTransactionCommit();
        IsHookedPy = true;
}

//just to make the code look cleaner
int IsEqual(const char* str1, const char* str2) {
    return strcmp(str1, str2) == 0;
}

DWORD WINAPI MainThread(HMODULE hModule)
{
    std::string ExitHook = "import sys\nimport os\ndef _exit(*var):pass\nsetattr(sys, 'exit', _exit)\nsetattr(__builtins__, 'exit', _exit)\nsetattr(os, '_exit', _exit)\n";
    std::string DumpStringsHook = "\n[(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]; open(DE4PYHOOKEEEEE99_ignore, 'w', encoding='utf-8').write('\\n'.join(f'{n} = {v}' for n, v in [(n, v) for n, v in globals().items() if isinstance(v, (str, dict, list, int))]))";
    std::string GetFunctionsHook = "\nimport inspect as de4pyhook3_ignore; de4pyhook2_ignore = lambda de4pyhook1_ignore: hex(id(de4pyhook1_ignore.__code__.co_code)) if hasattr(de4pyhook1_ignore, '__code__') else None; [open(DE4PYHOOKEEEEE99_ignore, 'a', encoding='utf-8').write(f\"{'function' if de4pyhook3_ignore.isfunction(m) else 'member'} name: {n}, address: {de4pyhook2_ignore(m)}\\n\") for n, m in de4pyhook3_ignore.getmembers(__import__('__main__'))]";
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
                else if (IsEqual(buffer, "ForceCrash")) {
                    SendMessageToPipe(pipe, "OK.");
                    DisconnectNamedPipe(pipe);
                    CloseHandle(pipe);
                    Force_crash();
                }
                else if (IsEqual(buffer, "GetAnalyzerHandle")) {
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
                else if (IsEqual(buffer, "MonitorFiles")) {
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
                else if (IsEqual(buffer, "UnMonitorFiles")) {
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
                else if (IsEqual(buffer, "MonitorProcesses")) {
                    if (pipe_analyzer != NULL)
                    {
                        if (IsHookedProcessMon)
                        {
                            SendMessageToPipe(pipe, "already monitoring.");
                        }
                        else
                        {
                            MonitorGeneralProcessBehavior(false);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (IsEqual(buffer, "UnMonitorProcesses")) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsHookedProcessMon)
                        {
                            SendMessageToPipe(pipe, "not monitoring in the first place.");
                        }
                        else
                        {
                            MonitorGeneralProcessBehavior(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (IsEqual(buffer, "MonitorConnections")) {
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
                else if (IsEqual(buffer, "UnMonitorConnections")) {
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
                else if (IsEqual(buffer, "DeattachDLL")) {
                    SendMessageToPipe(pipe, "OK.");
                    DisconnectNamedPipe(pipe);
                    CloseHandle(pipe);
                    unload_dll(hModule);
                }
                else if (IsEqual(buffer, "delExit")) {
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
                else if (std::string(buffer).rfind("DumpConnections", 0) == 0) {
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        std::string Path = lol.substr(ok + 2);
                        DWORD attrib = GetFileAttributesA(Path.c_str());
                        if (attrib != INVALID_FILE_ATTRIBUTES && (attrib & FILE_ATTRIBUTE_DIRECTORY) == 0)
                        {
                            if (pipe_analyzer != NULL)
                            {
                                if (!IsHookedConnectionsMon)
                                {
                                    SendMessageToPipe(pipe, "not monitoring in the first place.");
                                }
                                else
                                {
                                    strcpy_s(DumpPath, MAX_PATH, Path.c_str());
                                    DumpContent = TRUE;
                                    SendMessageToPipe(pipe, "OK.");
                                }
                            }
                            else
                            {
                                SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                            }
                        }
                        else
                        {
                            SendMessageToPipe(pipe, "File not found.");
                        }
                    }
                }
                else if (IsEqual(buffer, "StopDumpingConnections")) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!DumpContent)
                        {
                            SendMessageToPipe(pipe, "not dumping in the first place.");
                        }
                        else
                        {
                            DumpContent = FALSE;
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (std::string(buffer).rfind("DumpOpenSSL", 0) == 0) {
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        std::string Path = lol.substr(ok + 2);
                        DWORD attrib = GetFileAttributesA(Path.c_str());
                        if (attrib != INVALID_FILE_ATTRIBUTES && (attrib & FILE_ATTRIBUTE_DIRECTORY) == 0)
                        {
                            if (pipe_analyzer != NULL)
                            {
                                if (GetModuleHandle(L"libssl-1_1.dll") != NULL)
                                {
                                    strcpy_s(DumpSSLPath, MAX_PATH, Path.c_str());
                                    if(DumpSSL(false))
                                        SendMessageToPipe(pipe, "OK.");
                                    else
                                        SendMessageToPipe(pipe, "Failed to hook OpenSSL.");
                                }
                                else
                                {
                                    SendMessageToPipe(pipe, "OpenSSL library are not found in the target process.");
                                }
                            }
                            else
                            {
                                SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                            }
                        }
                        else
                        {
                            SendMessageToPipe(pipe, "File not found.");
                        }
                    }
                }
                else if (IsEqual(buffer, "StopDumpingSSL")) {
                    if (pipe_analyzer != NULL)
                    {
                        if (!IsDumping)
                        {
                            SendMessageToPipe(pipe, "not dumping in the first place.");
                        }
                        else
                        {
                            DumpSSL(true);
                            SendMessageToPipe(pipe, "OK.");
                        }
                    }
                    else
                    {
                        SendMessageToPipe(pipe, "Please do the \"GetAnalyzerHandle\" command before using this.");
                    }
                }
                else if (std::string(buffer).rfind("DumpPyc", 0) == 0) {
                    std::string lol(buffer);
                    size_t ok = lol.find("||");
                    if (ok != std::string::npos) {
                        std::string Path = lol.substr(ok + 2);
                            HMODULE PyDll = GetPythonDll();
                            if (PyDll != NULL)
                            {
                                WriteObject = (PyMarshal_WriteObjectToFile)GetProcAddress(PyDll, "PyMarshal_WriteObjectToFile");
                                if (WriteObject != NULL)
                                {
                                    try {
                                        SendMessageToPipe(pipe, "OK.");
                                        strcpy_s(PyDumpPath, sizeof(PyDumpPath), Path.c_str());
                                        DumpPythonCode(false);
                                    }
                                    catch (const std::exception& ex) {
                                        printf("%s", ex.what());
                                    }

                                    
                                }
                                else
                                {
                                    SendMessageToPipe(pipe, "couldn't import PyMarshal_WriteObjectToFile...");
                                }
                            }
                            else
                            {
                                SendMessageToPipe(pipe, "Python library are not found in the target process.");
                            }
                        }
                }
                else if (IsEqual(buffer, "StopDumpingPyc")) {
                    if (!IsHookedPy)
                    {
                        SendMessageToPipe(pipe, "not dumping in the first place.");
                    }
                    else
                    {
                        DumpPythonCode(true);
                        SendMessageToPipe(pipe, "OK.");
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
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    if (ul_reason_for_call == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(hModule);
        CloseHandle(CreateThread(0, 0, (LPTHREAD_START_ROUTINE)MainThread, hModule, 0, 0));
    }
    return TRUE;
}