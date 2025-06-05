* [packer](https://www.packer.io/)
* [packer integration with virtualbox](https://developer.hashicorp.com/packer/integrations/hashicorp/virtualbox)

```shell
packer plugins install github.com/hashicorp/virtualbox
```

* [packer unattended windows](https://developer.hashicorp.com/packer/guides/automatic-operating-system-installs/autounattend_windows)
* [packer windows examples by StefanScherer](https://github.com/StefanScherer/packer-windows)
* [answer files (win10)](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/update-windows-settings-and-scripts-create-your-own-answer-file-sxs?view=windows-10)
* [windows answer file generator (plus other tools)](https://www.windowsafg.com/index.html)

* [instructions for downloading Windows 10 ISO that includes `install.wim`](https://www.tenforums.com/installation-upgrade/201782-media-creation-tool-doesnt-create-wim-file-when-iso-chosen.html#post2503208)
* [modify iso to skip "Press any key to boot from CD or DVD" on windows](https://taylor.dev/removing-press-any-key-prompts-for-windows-install-automation/)
* [modify iso to skip "Press any key to boot from CD or DVD" on linux](https://unix.stackexchange.com/a/756423)


* [Hide Sensitive Data in an Answer File](https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/wsim/hide-sensitive-data-in-an-answer-file)

encoding:

```powershell
$PasswordPlainText = 'SomePassw0rd!'
$PasswordUTF16LE   = [System.Text.Encoding]::Unicode.GetBytes($PasswordPlainText + 'Password')
$PasswordBase64    = [System.Convert]::ToBase64String($PasswordUTF16LE)
$PasswordXml       = [xml]('<Password><Value>{0}</Value><PlainText>false</PlainText></Password>' -f $PasswordBase64)
Write-Output $PasswordXml.OuterXml

# or with simple indenting
Write-Output ([System.Xml.Linq.XDocument]::Parse($PasswordXml.OuterXml).ToString())
```

decoding:

```powershell
$PasswordBase64    = 'UwBvAG0AZQBQAGEAcwBzAHcAMAByAGQAIQBQAGEAcwBzAHcAbwByAGQA'
$PasswordUTF16LE   = [System.Convert]::FromBase64String($PasswordBase64)
$PasswordPlainText = [System.Text.Encoding]::Unicode.GetString($PasswordUTF16LE) -replace 'Password$', ''
Write-Output $PasswordPlainText
```




# create iso file for use with autounattend.xml answer file

Requires Windows ADK

Must run from elevated (run as administrator) "Deployment and Imaging Tools Environment" command prompt:

    C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\AMD64\Oscdimg\oscdimg.exe
        -j1           (both joliet and iso 9660 filesystems)
        -o            (encode duplicate files only once)
        -m            (ignore max size limit of iso)
        -lunattend    (label of iso)
        IN_FOLDER     (full path to folder with contents, including "autounattend.xml")
        OUT.iso       (full path to output iso file)









https://software.download.prss.microsoft.com/dbazure/Win10_22H2_English_x64v1.iso?t=fb0c8fe5-55fc-48b4-a26d-496340f1796a&e=1699025902&h=3f924c4cfbc0d410c68b1f93b47b19797c12085d4275b1a71154be9d8a330f94

https://software-static.download.prss.microsoft.com/dbazure/988969d5-f34g-4e03-ac9d-1f9786c66750/19045.2006.220908-0225.22h2_release_svc_refresh_CLIENTENTERPRISEEVAL_OEMRET_x64FRE_en-us.iso





    Steps:

    In VirtualBox, create a new VM:
        * Enable EFI
        * SATA/AHCI storage controller (Windows Setup under UEFI requires SATA or better)
            + Virtual harddrive (min: 20 GB)
            + Boot optical drive
                - Windows 10 Enterprise installation ISO
            + Optical drive for answer file
                - Add this file as "autounattend.xml" to the virtual ISO
        * Network Adapter 1
            + Host-only
            + Disconnect cable
        * Other configuration...
        * Launch VM
            - Except for "press any key to boot from CD or DVD", the install should be automated.

    Alternative ISO creation procedure using Windows Assessment and Deployment Kit (Windows ADK)
        * On a Windows computer:
            + Install Windows ADK https://learn.microsoft.com/en-us/windows-hardware/get-started/adk-install
            + Create an empty folder (name does not matter)
            + Copy "autounattend.xml" to the new folder
            + Start an elevated "Deployment and Imaging Tools Environment" command prompt
            + Run:
                oscdimg.exe -j1 -o -m -lunattend IN_FOLDER OUT.iso
              where:
                IN_FOLDER  is the full path to the new folder with "autounattend.xml"
                OUT.iso    is the full path to output ISO file
