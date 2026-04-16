import os

def create_desktop_file(icon_path, exe_path):
    """Create a .desktop file for the application."""
    desktop_file_path = os.path.join(os.path.expanduser("~/.local/share/applications"), "FloatingReminder.desktop")
    
    if not os.path.exists(desktop_file_path):
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(desktop_file_path), exist_ok=True)

        # Content of the .desktop file
        desktop_file_content = f"""[Desktop Entry]
Name=Floating Reminder
Comment=A reminder app to keep you focused
Exec=python3 {exe_path}
Icon= {icon_path}
Type=Application
Categories=Utility;Office;
StartupWMClass=WhatMattersMost
Terminal=false
        """.format(os.path.dirname(os.path.abspath(__file__)), os.path.dirname(os.path.abspath(__file__)))

        # Write to the .desktop file
        with open(desktop_file_path, 'w') as f:
            f.write(desktop_file_content)

        print(f".desktop file created at {desktop_file_path}")
    else:
        print(f".desktop file already exists at {desktop_file_path}")

    return desktop_file_path
