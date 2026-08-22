# Shared helper for Windows service-account user rights and credential validation.
# This file is intended to be dot-sourced by create-service-account.ps1 and register-scheduled-tasks.ps1.

Set-StrictMode -Version Latest

if (-not ("StockServer.WindowsAccountRights" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;

namespace StockServer
{
    public static class WindowsAccountRights
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_OBJECT_ATTRIBUTES
        {
            public int Length;
            public IntPtr RootDirectory;
            public IntPtr ObjectName;
            public uint Attributes;
            public IntPtr SecurityDescriptor;
            public IntPtr SecurityQualityOfService;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct LSA_UNICODE_STRING
        {
            public ushort Length;
            public ushort MaximumLength;
            public IntPtr Buffer;
        }

        private const uint POLICY_LOOKUP_NAMES = 0x00000800;
        private const uint POLICY_CREATE_ACCOUNT = 0x00000010;
        private const int LOGON32_LOGON_BATCH = 4;
        private const int LOGON32_PROVIDER_DEFAULT = 0;

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern uint LsaOpenPolicy(
            IntPtr SystemName,
            ref LSA_OBJECT_ATTRIBUTES ObjectAttributes,
            uint DesiredAccess,
            out IntPtr PolicyHandle);

        [DllImport("advapi32.dll")]
        private static extern uint LsaAddAccountRights(
            IntPtr PolicyHandle,
            IntPtr AccountSid,
            LSA_UNICODE_STRING[] UserRights,
            uint CountOfRights);

        [DllImport("advapi32.dll")]
        private static extern uint LsaEnumerateAccountRights(
            IntPtr PolicyHandle,
            IntPtr AccountSid,
            out IntPtr UserRights,
            out uint CountOfRights);

        [DllImport("advapi32.dll")]
        private static extern uint LsaClose(IntPtr PolicyHandle);

        [DllImport("advapi32.dll")]
        private static extern uint LsaFreeMemory(IntPtr Buffer);

        [DllImport("advapi32.dll")]
        private static extern int LsaNtStatusToWinError(uint Status);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool LogonUser(
            string lpszUsername,
            string lpszDomain,
            string lpszPassword,
            int dwLogonType,
            int dwLogonProvider,
            out IntPtr phToken);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private static IntPtr OpenPolicy(uint access)
        {
            LSA_OBJECT_ATTRIBUTES attrs = new LSA_OBJECT_ATTRIBUTES();
            attrs.Length = Marshal.SizeOf(typeof(LSA_OBJECT_ATTRIBUTES));
            IntPtr handle;
            uint status = LsaOpenPolicy(IntPtr.Zero, ref attrs, access, out handle);
            if (status != 0)
            {
                throw new Win32Exception(LsaNtStatusToWinError(status), "LsaOpenPolicy failed");
            }
            return handle;
        }

        private static IntPtr SidToNative(SecurityIdentifier sid)
        {
            byte[] bytes = new byte[sid.BinaryLength];
            sid.GetBinaryForm(bytes, 0);
            IntPtr ptr = Marshal.AllocHGlobal(bytes.Length);
            Marshal.Copy(bytes, 0, ptr, bytes.Length);
            return ptr;
        }

        private static LSA_UNICODE_STRING MakeUnicodeString(string value, out IntPtr buffer)
        {
            buffer = Marshal.StringToHGlobalUni(value);
            LSA_UNICODE_STRING item = new LSA_UNICODE_STRING();
            item.Buffer = buffer;
            item.Length = checked((ushort)(value.Length * 2));
            item.MaximumLength = checked((ushort)((value.Length + 1) * 2));
            return item;
        }

        public static string[] GetRights(SecurityIdentifier sid)
        {
            IntPtr policy = IntPtr.Zero;
            IntPtr sidPtr = IntPtr.Zero;
            IntPtr rightsPtr = IntPtr.Zero;
            try
            {
                policy = OpenPolicy(POLICY_LOOKUP_NAMES);
                sidPtr = SidToNative(sid);
                uint count;
                uint status = LsaEnumerateAccountRights(policy, sidPtr, out rightsPtr, out count);
                if (status != 0)
                {
                    int error = LsaNtStatusToWinError(status);
                    if (error == 2)
                    {
                        return new string[0];
                    }
                    throw new Win32Exception(error, "LsaEnumerateAccountRights failed");
                }

                List<string> result = new List<string>();
                int itemSize = Marshal.SizeOf(typeof(LSA_UNICODE_STRING));
                for (int i = 0; i < count; i++)
                {
                    IntPtr itemPtr = IntPtr.Add(rightsPtr, i * itemSize);
                    LSA_UNICODE_STRING item = (LSA_UNICODE_STRING)Marshal.PtrToStructure(itemPtr, typeof(LSA_UNICODE_STRING));
                    string text = Marshal.PtrToStringUni(item.Buffer, item.Length / 2);
                    if (!String.IsNullOrEmpty(text))
                    {
                        result.Add(text);
                    }
                }
                return result.ToArray();
            }
            finally
            {
                if (rightsPtr != IntPtr.Zero) { LsaFreeMemory(rightsPtr); }
                if (sidPtr != IntPtr.Zero) { Marshal.FreeHGlobal(sidPtr); }
                if (policy != IntPtr.Zero) { LsaClose(policy); }
            }
        }

        public static void AddRight(SecurityIdentifier sid, string right)
        {
            IntPtr policy = IntPtr.Zero;
            IntPtr sidPtr = IntPtr.Zero;
            IntPtr rightBuffer = IntPtr.Zero;
            try
            {
                policy = OpenPolicy(POLICY_LOOKUP_NAMES | POLICY_CREATE_ACCOUNT);
                sidPtr = SidToNative(sid);
                LSA_UNICODE_STRING[] rights = new LSA_UNICODE_STRING[1];
                rights[0] = MakeUnicodeString(right, out rightBuffer);
                uint status = LsaAddAccountRights(policy, sidPtr, rights, 1);
                if (status != 0)
                {
                    throw new Win32Exception(LsaNtStatusToWinError(status), "LsaAddAccountRights failed");
                }
            }
            finally
            {
                if (rightBuffer != IntPtr.Zero) { Marshal.FreeHGlobal(rightBuffer); }
                if (sidPtr != IntPtr.Zero) { Marshal.FreeHGlobal(sidPtr); }
                if (policy != IntPtr.Zero) { LsaClose(policy); }
            }
        }

        public static int ValidateLocalPassword(string domain, string username, string password)
        {
            IntPtr token = IntPtr.Zero;
            try
            {
                if (LogonUser(username, domain, password, LOGON32_LOGON_BATCH, LOGON32_PROVIDER_DEFAULT, out token))
                {
                    return 0;
                }
                return Marshal.GetLastWin32Error();
            }
            finally
            {
                if (token != IntPtr.Zero) { CloseHandle(token); }
            }
        }
    }
}
'@
}

function Resolve-LocalAccountSid {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $identity = if ($AccountName.Contains("\")) { $AccountName } else { "$env:COMPUTERNAME\$AccountName" }
    try {
        $ntAccount = New-Object Security.Principal.NTAccount -ArgumentList $identity
        return $ntAccount.Translate([Security.Principal.SecurityIdentifier])
    }
    catch {
        throw "无法解析本地账号SID：$identity。$($_.Exception.Message)"
    }
}

function Get-LocalAccountRights {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $sid = Resolve-LocalAccountSid -AccountName $AccountName
    return @([StockServer.WindowsAccountRights]::GetRights($sid))
}

function Assert-ServiceAccountBatchLogonRight {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $rights = @(Get-LocalAccountRights -AccountName $AccountName)
    if ($rights -contains "SeDenyBatchLogonRight") {
        throw "服务账号${AccountName}被授予了‘拒绝作为批处理作业登录(SeDenyBatchLogonRight)’，Windows计划任务将无法启动。请先移除拒绝权限。"
    }
    if ($rights -notcontains "SeBatchLogonRight") {
        throw "服务账号${AccountName}缺少‘作为批处理作业登录(SeBatchLogonRight)’权限。请先运行create-service-account.ps1准备服务账号。"
    }
    Write-Host "PASS：${AccountName} 已具备作为批处理作业登录权限，且未发现显式拒绝权限。"
}

function Ensure-ServiceAccountBatchLogonRight {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $sid = Resolve-LocalAccountSid -AccountName $AccountName
    $rights = @([StockServer.WindowsAccountRights]::GetRights($sid))
    if ($rights -contains "SeDenyBatchLogonRight") {
        throw "服务账号${AccountName}被授予了‘拒绝作为批处理作业登录(SeDenyBatchLogonRight)’；为避免绕过安全策略，本脚本不会自动移除拒绝权限。"
    }
    if ($rights -notcontains "SeBatchLogonRight") {
        [StockServer.WindowsAccountRights]::AddRight($sid, "SeBatchLogonRight")
        Write-Host "已为${AccountName}授予‘作为批处理作业登录(SeBatchLogonRight)’权限。"
    }
    Assert-ServiceAccountBatchLogonRight -AccountName $AccountName
}

function Test-LocalServiceAccountPassword {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$AccountName,
        [Parameter(Mandatory = $true)][string]$PlainPassword
    )

    $userName = $AccountName
    $domain = $env:COMPUTERNAME
    if ($AccountName.Contains("\")) {
        $parts = $AccountName.Split("\", 2)
        $domain = $parts[0]
        $userName = $parts[1]
    }
    $errorCode = [StockServer.WindowsAccountRights]::ValidateLocalPassword($domain, $userName, $PlainPassword)
    return $errorCode
}
