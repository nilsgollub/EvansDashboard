import sys
import paramiko
import time

def safe_write(text):
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'ascii'
        sys.stdout.write(text.encode(encoding, errors='replace').decode(encoding))
    sys.stdout.flush()

def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'ascii'
        print(text.encode(encoding, errors='replace').decode(encoding))

def run_ssh_commands(host, username, password, commands):
    safe_print(f"Connecting to {host} as {username}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=username, password=password, timeout=10)
        safe_print("Connected successfully!")
        
        for cmd in commands:
            safe_print(f"\n--- Running: {cmd} ---")
            # We use invoke_shell for interactive or complex scripts,
            # or exec_command for normal execution.
            # Since the setup script is interactive, we will use an interactive shell!
            transport = ssh.get_transport()
            channel = transport.open_session()
            channel.get_pty()
            channel.exec_command(cmd)
            
            try:
                # Read output in real-time
                while True:
                    if channel.recv_ready():
                        output = channel.recv(1024).decode('utf-8', errors='ignore')
                        safe_write(output)
                    
                    if channel.exit_status_ready():
                        break
                    time.sleep(0.1)
                
                # Print remaining output
                while channel.recv_ready():
                    output = channel.recv(1024).decode('utf-8', errors='ignore')
                    safe_write(output)
                    
                safe_print(f"\nCommand finished with exit code: {channel.recv_exit_status()}")
            except Exception as cmd_error:
                if "reboot" in cmd:
                    safe_print("\nConnection closed. This is expected as the Pi is rebooting! *")
                    break
                else:
                    safe_print(f"\nError running command: {cmd_error}")
                    raise cmd_error
            
    except Exception as e:
        if "reboot" in str(e) or "Connection reset" in str(e):
            safe_print("\nConnection closed. This is expected as the Pi is rebooting! *")
        else:
            safe_print(f"Error: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_ssh.py <host> <username> <password> [<hotspot_ssid> <hotspot_pw>]")
        sys.exit(1)
        
    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    
    # We will run:
    # 1. Update git repo
    # 2. Run the setup script!
    commands = [
        "cd ~/EvansDashboard && git reset --hard && git pull && chmod +x setup_fresh_pi.sh"
    ]
    
    setup_cmd = "cd ~/EvansDashboard && ./setup_fresh_pi.sh --non-interactive --reboot"
    if len(sys.argv) >= 6:
        ssid = sys.argv[4]
        pw = sys.argv[5]
        setup_cmd += f" --hotspot-ssid '{ssid}' --hotspot-pw '{pw}'"
        
    commands.append(setup_cmd)
    
    run_ssh_commands(host, username, password, commands)
