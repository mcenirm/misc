import winreg
import ctypes


def show_legal_notice():
    # Registry path for legal notices
    reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

    try:
        # Open the registry key
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
            # Retrieve LegalNoticeText and LegalNoticeCaption
            notice_text, _ = winreg.QueryValueEx(key, "LegalNoticeText")
            notice_title, _ = winreg.QueryValueEx(key, "LegalNoticeCaption")

            # Fallback if values are empty
            if not notice_text:
                notice_text = "No legal notice text found in registry."
            if not notice_title:
                notice_title = "Legal Notice"

    except FileNotFoundError:
        notice_text = "Registry key not found."
        notice_title = "Error"
    except Exception as e:
        notice_text = f"An error occurred: {e}"
        notice_title = "Error"

    # Display the message box using the Windows API
    # 0x40 is the flag for the 'Information' icon
    x = ctypes.windll.user32.MessageBoxTimeoutW(
        0,
        notice_text,
        notice_title,
        0x0,
        0x0,
        3000,
    )
    print("MessageBox returned:", repr(x))


if __name__ == "__main__":
    show_legal_notice()
