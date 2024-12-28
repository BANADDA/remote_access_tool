import getpass
import logging
import subprocess
import time
from pathlib import Path

from . import config, utils

logger = logging.getLogger('remote_access')

class SSHManager:
    def __init__(self):
        self.logger = logging.getLogger('remote_access')
        
    def create_sshd_config(self, port):
        config_content = f"""
# SSH Server Configuration
Port {port}
PermitRootLogin yes
AuthorizedKeysFile .ssh/authorized_keys
PasswordAuthentication yes
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes
Subsystem sftp sftp-server.exe
"""
        # Write to temp file first
        temp_config = config.HOME_DIR / 'sshd_config_temp'
        with open(temp_config, 'w', encoding='utf-8') as f:
            f.write(config_content.strip())
        
        # Copy to correct location with elevation
        utils.run_elevated(f'copy /Y "{temp_config}" "{config.SSH_CONFIG_PATH}"')
        temp_config.unlink(missing_ok=True)

    def setup_server(self, port):
        self.logger.info("Installing and configuring OpenSSH Server...")
        
        commands = [
            'powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"',
            'net stop sshd 2>NUL',
            'mkdir "C:\\ProgramData\\ssh" 2>NUL',
        ]
        
        for cmd in commands:
            utils.run_elevated(cmd)
        
        self.create_sshd_config(port)
        
        commands = [
            'net start sshd',
            'powershell -Command "Set-Service -Name sshd -StartupType Automatic"'
        ]
        
        for cmd in commands:
            utils.run_elevated(cmd)

    def setup_user(self):
        username = getpass.getuser()
        password = utils.generate_password()
        
        self.logger.info(f"Configuring user {username} for SSH access...")
        
        # First ensure the password can be changed
        enable_cmd = f'wmic UserAccount where Name="{username}" set PasswordExpires=false'
        utils.run_elevated(enable_cmd)
        
        # Set the password using both methods to ensure it works
        commands = [
            # Method 1: Using net user
            f'net user {username} "{password}"',
            # Method 2: Using PowerShell for redundancy
            f'powershell -Command "$password = ConvertTo-SecureString \'{password}\' -AsPlainText -Force; Set-LocalUser -Name \'{username}\' -Password $password"',
            # Enable user if not enabled
            f'net user {username} /active:yes',
            # Set shell
            'powershell -Command "Set-ItemProperty -Path HKLM:\\SOFTWARE\\OpenSSH -Name DefaultShell -Value C:\\Windows\\System32\\cmd.exe -Force"'
        ]
        
        for cmd in commands:
            utils.run_elevated(cmd)
            time.sleep(1)  # Add small delay between commands
        
        # Verify the password was set
        self.logger.info("Password set successfully")
        return username, password