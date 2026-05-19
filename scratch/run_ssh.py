import sys
import paramiko
import time

def run_ssh_commands(host, username, password, commands):
    print(f"Connecting to {host} as {username}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(host, username=username, password=password, timeout=10)
        print("Connected successfully!")
        
        for cmd in commands:
            print(f"\n--- Running: {cmd} ---")
            # We use invoke_shell for interactive or complex scripts,
            # or exec_command for normal execution.
            # Since the setup script is interactive, we will use an interactive shell!
            transport = ssh.get_transport()
            channel = transport.open_session()
            channel.get_pty()
            channel.exec_command(cmd)
            
            # Read output in real-time
            while True:
                if channel.recv_ready():
                    output = channel.recv(1024).decode('utf-8', errors='ignore')
                    sys.stdout.write(output)
                    sys.stdout.flush()
                
                # If the script asks for input (e.g. y/n or password), we can automatically handle it!
                # Wait, the script asks:
                # 1. sudo password? Since we run as sudo, it might ask for sudo password.
                # 2. "Möchtest du jetzt einen Fallback-Hotspot einrichten? (y/n)"
                # 3. Hotspot SSID
                # 4. Hotspot Password
                # 5. "Möchtest du den Pi jetzt neu starten? (y/n)"
                # Let's detect these prompts and handle them if needed, or wait:
                # Since the user requested me to run it, let's look for prompts.
                # Wait, if we run it non-interactively, can we pre-seed the inputs?
                # Actually, the user can just let us run it and we can automatically answer "n" to the hotspot for now,
                # or we can ask them for the hotspot credentials too!
                # Let's check if we can stream input/output.
                
                if channel.exit_status_ready():
                    break
                time.sleep(0.1)
            
            # Print remaining output
            while channel.recv_ready():
                output = channel.recv(1024).decode('utf-8', errors='ignore')
                sys.stdout.write(output)
                sys.stdout.flush()
                
            print(f"\nCommand finished with exit code: {channel.recv_exit_status()}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python run_ssh.py <host> <username> <password>")
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
    
    run_ssh_commands(host, username, password, commands)
