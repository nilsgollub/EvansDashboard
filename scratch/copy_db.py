import sys
import os
import paramiko

def progress_callback(transferred, total):
    percent = (transferred / total) * 100
    sys.stdout.write(f"\rUploading: {percent:.2f}% ({transferred}/{total} bytes)")
    sys.stdout.flush()

def main():
    host = "192.168.1.202"
    username = "nilsgollub"
    password = "JhiswenP3003!"
    local_path = "switzerland_roads.db"
    remote_path = "/home/nilsgollub/EvansDashboard/switzerland_roads.db"
    
    if not os.path.exists(local_path):
        print(f"Error: Local file {local_path} not found!")
        sys.exit(1)
        
    print(f"Connecting to {host} as {username}...")
    try:
        transport = paramiko.Transport((host, 22))
        transport.connect(username=username, password=password)
        
        sftp = paramiko.SFTPClient.from_transport(transport)
        print(f"Starting upload of {local_path} to {remote_path}...")
        
        sftp.put(local_path, remote_path, callback=progress_callback)
        print("\nUpload completed successfully!")
        
        sftp.close()
        transport.close()
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
