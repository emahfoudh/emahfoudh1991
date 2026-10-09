<#
.SYNOPSIS
    Exports everything needed for the Microsoft 365 license optimisation review.

.DESCRIPTION
    Read-only. Produces one folder of CSVs (and a .zip of it):

      01_Users_SignIn.csv            every user, licenses, enabled/blocked, last sign-in (needs Entra ID P1)
      02_ActiveUsers_D180.csv        last activity per service (Exchange, OneDrive, SharePoint, Teams)
      03_EmailAppsUsage_D180.csv     Outlook Windows / Mac / mobile / web per user
      04_M365AppsUsage_D180.csv      desktop vs web vs mobile Word/Excel/PowerPoint/Outlook per user
      05_MailboxUsage_D180.csv       mailbox size, quota, item count
      06_OneDriveUsage_D180.csv      OneDrive storage per user
      07_TeamsUsage_D180.csv         Teams activity per user
      08_CopilotUsage_D180.csv       Copilot last activity per app (skipped if the tenant does not expose it)
      09_Mailboxes_EXO.csv           every mailbox: type (user/shared/room), size, archive, holds, forwarding
      10_Subscriptions.csv           seats bought, status, trial flag, next renewal / lifecycle date
      11_GroupLicenseErrors.csv      members of license-assigning groups whose license failed

    The only change the script makes is temporarily switching off "Display concealed user names"
    in report settings (so reports show real UPNs), and it restores the original value at the end.
    Use -KeepConcealedNames to skip that.

    Prices are NOT in the tenant when you buy through a reseller (CSP); get those from the invoice.

.REQUIREMENTS
    PowerShell 7+ (Windows PowerShell 5.1 also works).
    Install-Module Microsoft.Graph.Authentication, ExchangeOnlineManagement -Scope CurrentUser
    Sign in as Global Admin, or Global Reader + Reports Reader (Global Reader cannot change the
    report setting; run with -KeepConcealedNames in that case).

.EXAMPLE
    .\Export-M365LicenseData.ps1
    .\Export-M365LicenseData.ps1 -OutputFolder C:\Temp\M365Audit -SkipExchange
#>
[CmdletBinding()]
param(
    [string]$OutputFolder = (Join-Path $PWD "M365Audit_$(Get-Date -Format yyyyMMdd_HHmm)"),
    [switch]$KeepConcealedNames,
    [switch]$SkipExchange
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
function Out-Csv($Data, $Name) {
    $path = Join-Path $OutputFolder $Name
    $Data | Export-Csv -Path $path -NoTypeInformation -Encoding UTF8
    Write-Host "  -> $Name ($(@($Data).Count) rows)" -ForegroundColor Green
}

# Follows @odata.nextLink until every page is collected.
function Get-GraphAll([string]$Uri, [hashtable]$Headers = @{}) {
    $items = [System.Collections.Generic.List[object]]::new()
    while ($Uri) {
        $resp = Invoke-MgGraphRequest -Method GET -Uri $Uri -Headers $Headers -OutputType PSObject
        if ($resp.value) { $items.AddRange([object[]]$resp.value) }
        $Uri = $resp.'@odata.nextLink'
    }
    $items
}

# Usage reports come back as CSV; save them straight to disk.
function Save-Report([string]$Function, [string]$Name, [string]$Version = 'v1.0') {
    $uri = "https://graph.microsoft.com/$Version/reports/$Function(period='D180')?`$format=text/csv"
    try {
        Invoke-MgGraphRequest -Method GET -Uri $uri -OutputFilePath (Join-Path $OutputFolder $Name)
        Write-Host "  -> $Name" -ForegroundColor Green
    } catch {
        Write-Warning "  $Name skipped: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------- Graph sign-in
Write-Host "Connecting to Microsoft Graph..." -ForegroundColor Cyan
$scopes = @('Reports.Read.All', 'User.Read.All', 'AuditLog.Read.All', 'Directory.Read.All',
            'Organization.Read.All', 'GroupMember.Read.All')
if (-not $KeepConcealedNames) { $scopes += 'ReportSettings.ReadWrite.All' }
Connect-MgGraph -Scopes $scopes -NoWelcome

$originalConcealed = $null
try {
    if (-not $KeepConcealedNames) {
        $settings = Invoke-MgGraphRequest -Method GET -Uri 'https://graph.microsoft.com/v1.0/admin/reportSettings'
        $originalConcealed = [bool]$settings.displayConcealedNames
        if ($originalConcealed) {
            Write-Host "Temporarily showing real names in reports (will be restored)..." -ForegroundColor Yellow
            Invoke-MgGraphRequest -Method PATCH -Uri 'https://graph.microsoft.com/v1.0/admin/reportSettings' `
                -Body (@{ displayConcealedNames = $false } | ConvertTo-Json)
            Start-Sleep -Seconds 60   # setting takes a moment to apply to report endpoints
        }
    }

    # ------------------------------------------------------------ SKU name lookup
    $skus = Get-GraphAll 'https://graph.microsoft.com/v1.0/subscribedSkus'
    $skuName = @{}
    foreach ($s in $skus) { $skuName[$s.skuId] = $s.skuPartNumber }

    # ------------------------------------------------------------ 01 users + sign-in
    Write-Host "Users and last sign-in..." -ForegroundColor Cyan
    $select = 'id,displayName,userPrincipalName,accountEnabled,userType,createdDateTime,jobTitle,' +
              'department,officeLocation,country,usageLocation,assignedLicenses,signInActivity'
    try {
        $users = Get-GraphAll "https://graph.microsoft.com/v1.0/users?`$select=$select&`$top=999"
    } catch {
        Write-Warning "signInActivity not available (needs Entra ID P1 + AuditLog.Read.All); exporting without it."
        $users = Get-GraphAll "https://graph.microsoft.com/v1.0/users?`$select=$($select -replace ',signInActivity')&`$top=999"
    }
    Out-Csv ($users | ForEach-Object {
        [pscustomobject]@{
            UserPrincipalName         = $_.userPrincipalName
            DisplayName               = $_.displayName
            AccountEnabled            = $_.accountEnabled
            UserType                  = $_.userType
            Created                   = $_.createdDateTime
            JobTitle                  = $_.jobTitle
            Department                = $_.department
            Office                    = $_.officeLocation
            Country                   = $_.country
            UsageLocation             = $_.usageLocation
            Licenses                  = ($_.assignedLicenses | ForEach-Object { $skuName[$_.skuId] }) -join '+'
            LastSignIn                = $_.signInActivity.lastSignInDateTime
            LastNonInteractiveSignIn  = $_.signInActivity.lastNonInteractiveSignInDateTime
            LastSuccessfulSignIn      = $_.signInActivity.lastSuccessfulSignInDateTime
        }
    }) '01_Users_SignIn.csv'

    # ------------------------------------------------------------ 02-08 usage reports
    Write-Host "Usage reports (180 days)..." -ForegroundColor Cyan
    Save-Report 'getOffice365ActiveUserDetail'     '02_ActiveUsers_D180.csv'
    Save-Report 'getEmailAppUsageUserDetail'       '03_EmailAppsUsage_D180.csv'
    Save-Report 'getM365AppUserDetail'             '04_M365AppsUsage_D180.csv'
    Save-Report 'getMailboxUsageDetail'            '05_MailboxUsage_D180.csv'
    Save-Report 'getOneDriveUsageAccountDetail'    '06_OneDriveUsage_D180.csv'
    Save-Report 'getTeamsUserActivityUserDetail'   '07_TeamsUsage_D180.csv'
    try {
        $copilot = Get-GraphAll "https://graph.microsoft.com/beta/reports/getMicrosoft365CopilotUsageUserDetail(period='D180')"
        Out-Csv $copilot '08_CopilotUsage_D180.csv'
    } catch {
        Write-Warning "  08_CopilotUsage_D180.csv skipped: $($_.Exception.Message)"
    }

    # ------------------------------------------------------------ 10 subscriptions
    Write-Host "Subscriptions and renewal dates..." -ForegroundColor Cyan
    try {
        $subs = Get-GraphAll 'https://graph.microsoft.com/v1.0/directory/subscriptions'
        Out-Csv ($subs | ForEach-Object {
            [pscustomobject]@{
                Product           = $_.skuPartNumber
                Status            = $_.status
                TotalLicenses     = $_.totalLicenses
                IsTrial           = $_.isTrial
                Created           = $_.createdDateTime
                NextLifecycleDate = $_.nextLifecycleDateTime
            }
        }) '10_Subscriptions.csv'
    } catch {
        Write-Warning "  Subscriptions skipped: $($_.Exception.Message)"
    }
    # Seats bought vs assigned (same as the Licenses page)
    Out-Csv ($skus | ForEach-Object {
        [pscustomobject]@{
            Product  = $_.skuPartNumber
            Bought   = $_.prepaidUnits.enabled
            Warning  = $_.prepaidUnits.warning
            Assigned = $_.consumedUnits
        }
    }) '10b_SeatsBoughtVsAssigned.csv'

    # ------------------------------------------------------------ 11 group license errors
    Write-Host "Group-based licensing errors..." -ForegroundColor Cyan
    $groups = Get-GraphAll 'https://graph.microsoft.com/v1.0/groups?$select=id,displayName,assignedLicenses&$top=999' |
              Where-Object { $_.assignedLicenses.Count -gt 0 }
    $errors = foreach ($g in $groups) {
        $members = Get-GraphAll "https://graph.microsoft.com/v1.0/groups/$($g.id)/membersWithLicenseErrors?`$select=id,userPrincipalName"
        foreach ($m in $members) {
            [pscustomobject]@{
                Group             = $g.displayName
                GroupLicenses     = ($g.assignedLicenses | ForEach-Object { $skuName[$_.skuId] }) -join '+'
                UserPrincipalName = $m.userPrincipalName
            }
        }
    }
    Out-Csv $errors '11_GroupLicenseErrors.csv'
}
finally {
    if ($originalConcealed) {
        Invoke-MgGraphRequest -Method PATCH -Uri 'https://graph.microsoft.com/v1.0/admin/reportSettings' `
            -Body (@{ displayConcealedNames = $true } | ConvertTo-Json)
        Write-Host "Report name concealment restored." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- 09 Exchange mailboxes
if (-not $SkipExchange) {
    Write-Host "Connecting to Exchange Online (mailbox sizes, holds; ~10-20 min for 1,400 mailboxes)..." -ForegroundColor Cyan
    Connect-ExchangeOnline -ShowBanner:$false
    $bytes = { param($s) if ("$s" -match '\(([\d,]+) bytes\)') { [math]::Round(($Matches[1] -replace ',') / 1GB, 2) } }
    $mbx = Get-EXOMailbox -ResultSize Unlimited -Properties ArchiveStatus, LitigationHoldEnabled, InPlaceHolds,
           RetentionPolicy, ForwardingSmtpAddress, ForwardingAddress, ProhibitSendReceiveQuota
    $i = 0
    $rows = foreach ($m in $mbx) {
        $i++
        Write-Progress -Activity 'Mailbox statistics' -Status $m.UserPrincipalName -PercentComplete ($i / $mbx.Count * 100)
        $st = Get-EXOMailboxStatistics -Identity $m.ExternalDirectoryObjectId -Properties LastUserActionTime -ErrorAction SilentlyContinue
        $ar = if ($m.ArchiveStatus -eq 'Active') {
            Get-EXOMailboxStatistics -Identity $m.ExternalDirectoryObjectId -Archive -ErrorAction SilentlyContinue
        }
        [pscustomobject]@{
            UserPrincipalName  = $m.UserPrincipalName
            PrimarySmtpAddress = $m.PrimarySmtpAddress
            MailboxType        = $m.RecipientTypeDetails
            SizeGB             = & $bytes $st.TotalItemSize
            ItemCount          = $st.ItemCount
            LastUserAction     = $st.LastUserActionTime
            QuotaGB            = & $bytes $m.ProhibitSendReceiveQuota
            ArchiveStatus      = $m.ArchiveStatus
            ArchiveSizeGB      = & $bytes $ar.TotalItemSize
            LitigationHold     = $m.LitigationHoldEnabled
            InPlaceHolds       = ($m.InPlaceHolds -join ';')
            RetentionPolicy    = $m.RetentionPolicy
            ForwardingTo       = "$($m.ForwardingSmtpAddress)$($m.ForwardingAddress)"
        }
    }
    Write-Progress -Activity 'Mailbox statistics' -Completed
    Out-Csv $rows '09_Mailboxes_EXO.csv'
    Disconnect-ExchangeOnline -Confirm:$false
}

Disconnect-MgGraph | Out-Null
$zip = "$OutputFolder.zip"
Compress-Archive -Path "$OutputFolder\*" -DestinationPath $zip -Force
Write-Host "`nDone. Upload this file: $zip" -ForegroundColor Cyan
