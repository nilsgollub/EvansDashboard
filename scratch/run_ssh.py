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
        retries = 5
        for attempt in range(1, retries + 1):
            try:
                ssh.connect(host, username=username, password=password, timeout=30, banner_timeout=60)
                safe_print("Connected successfully!")
                break
            except Exception as conn_err:
                if attempt == retries:
                    raise conn_err
                safe_print(f"Connection attempt {attempt} failed: {conn_err}. Retrying in 5 seconds...")
                time.sleep(5)
            
        for cmd in commands:
            safe_print(f"\n--- Running: {cmd} ---")
            transport = ssh.get_transport()
            channel = transport.open_session()
            channel.get_pty()
            channel.exec_command(cmd)
            
            try:
                # Read output in real-time
                sudo_prompt_seen = False
                while True:
                    if channel.recv_ready():
                        output = channel.recv(1024).decode('utf-8', errors='ignore')
                        safe_write(output)
                        if "password for" in output.lower() and not sudo_prompt_seen:
                            channel.send(password + '\n')
                            sudo_prompt_seen = True
                    
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
    
    commands = [
        "systemctl --no-pager status evans-dashboard.service",
        "tail -n 25 ~/dashboard.log || true"
    ]
    
    run_ssh_commands(host, username, password, commands)
